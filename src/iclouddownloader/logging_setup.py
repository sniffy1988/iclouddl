from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import LogRecord

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_RESET = "\033[0m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_LEVEL_ANSI: dict[int, str] = {
    logging.DEBUG: "\033[36m",  # cyan
    logging.INFO: "\033[32m",  # green
    logging.WARNING: "\033[33;1m",  # bold yellow
    logging.ERROR: "\033[31;1m",  # bold red
    logging.CRITICAL: "\033[35;1;7m",  # bold magenta, reverse video
}
_LOGGER_ANSI = "\033[34m"  # blue
MAX_STORED_LOGS = 5000
LOG_LEVEL_NAMES = ("OFF", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_NAME_TO_LEVEL: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_db_queue: queue.Queue[dict] | None = None
_db_worker: threading.Thread | None = None
_configured = False

_QUIET_LOGGERS = ("httpx", "httpcore", "urllib3", "apscheduler", "telegram", "asyncio")


@dataclass(frozen=True)
class LoggingOptions:
    level_name: str
    console_level: int
    db_level: int
    persist_to_db: bool

    @property
    def debug_enabled(self) -> bool:
        return self.level_name == "DEBUG"


def normalize_log_level(name: str | None) -> str:
    if not name:
        return "OFF"
    key = str(name).strip().upper()
    if key in _NAME_TO_LEVEL:
        return key
    if key == "OFF":
        return "OFF"
    return "OFF"


def _level_from_settings_row(settings) -> str:
    level = normalize_log_level(getattr(settings, "logging_level", None))
    if level == "OFF" and bool(getattr(settings, "debug_logging_enabled", False)):
        return "DEBUG"
    return level


def _read_options() -> LoggingOptions:
    try:
        from iclouddownloader.services.runtime_settings_service import get_effective_settings

        settings = get_effective_settings()
        level_name = _level_from_settings_row(settings)
    except Exception:
        level_name = "OFF"

    if level_name == "OFF":
        return LoggingOptions(
            level_name="OFF",
            console_level=logging.INFO,
            db_level=logging.INFO,
            persist_to_db=False,
        )

    numeric = _NAME_TO_LEVEL[level_name]
    return LoggingOptions(
        level_name=level_name,
        console_level=numeric,
        db_level=numeric,
        persist_to_db=True,
    )


def is_debug_logging_enabled() -> bool:
    return _read_options().debug_enabled


def is_logging_enabled() -> bool:
    return _read_options().persist_to_db


def get_logging_level() -> str:
    return _read_options().level_name


def should_log_http_requests() -> bool:
    opts = _read_options()
    return opts.persist_to_db and opts.console_level <= logging.INFO


def _ensure_db_worker() -> queue.Queue[dict]:
    global _db_queue, _db_worker
    if _db_queue is None:
        _db_queue = queue.Queue(maxsize=2000)
    if _db_worker is None or not _db_worker.is_alive():
        _db_worker = threading.Thread(target=_db_worker_loop, name="app-log-writer", daemon=True)
        _db_worker.start()
    return _db_queue


def _db_worker_loop() -> None:
    assert _db_queue is not None
    while True:
        try:
            first = _db_queue.get()
        except Exception:
            continue
        batch = [first]
        while len(batch) < 100:
            try:
                batch.append(_db_queue.get_nowait())
            except queue.Empty:
                break
        _flush_log_batch(batch)


def _flush_log_batch(batch: list[dict]) -> None:
    if not batch:
        return
    try:
        from sqlalchemy import delete, func, select

        from iclouddownloader.db.models import AppLog
        from iclouddownloader.db.session import get_session_factory

        db = get_session_factory()()
        try:
            for row in batch:
                db.add(AppLog(**row))
            db.commit()
            count = db.scalar(select(func.count()).select_from(AppLog)) or 0
            if count > MAX_STORED_LOGS:
                excess = int(count) - MAX_STORED_LOGS
                ids = [
                    r[0]
                    for r in db.execute(
                        select(AppLog.id).order_by(AppLog.id.asc()).limit(excess)
                    ).all()
                ]
                if ids:
                    db.execute(delete(AppLog).where(AppLog.id.in_(ids)))
                    db.commit()
        finally:
            db.close()
    except Exception:
        logging.getLogger(__name__).exception("Failed to persist app logs to database")


def console_use_color() -> bool:
    """True when stderr should get ANSI colors (TTY, FORCE_COLOR; not NO_COLOR)."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("ICLD_LOG_COLOR", "1").lower() in ("0", "false", "no"):
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("CLICOLOR_FORCE"):
        return True
    try:
        return sys.stderr.isatty()
    except Exception:
        return False


class ColoredConsoleFormatter(logging.Formatter):
    """ANSI-colored console lines; plain text when use_color is False."""

    def __init__(self, *, use_color: bool = True, datefmt: str = "%Y-%m-%d %H:%M:%S") -> None:
        super().__init__(datefmt=datefmt)
        self._use_color = use_color

    def format(self, record: LogRecord) -> str:
        ts = self.formatTime(record, self.datefmt)
        message = record.getMessage()
        if not self._use_color:
            line = f"{ts} {record.levelname} [{record.name}] {message}"
        else:
            color = _LEVEL_ANSI.get(record.levelno, "")
            level = f"{color}{_BOLD}{record.levelname:<8}{_RESET}"
            logger_part = f"{_LOGGER_ANSI}[{record.name}]{_RESET}"
            line = f"{_DIM}{ts}{_RESET} {level} {logger_part} {message}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        elif record.exc_text:
            line += "\n" + record.exc_text
        return line


class DatabaseLogHandler(logging.Handler):
    """Async queue writer when logging_level is not OFF."""

    def emit(self, record: LogRecord) -> None:
        opts = _read_options()
        if not opts.persist_to_db:
            return
        if record.levelno < opts.db_level:
            return
        try:
            message = record.getMessage()
            if len(message) > 8000:
                message = message[:8000] + "…"
            exc = None
            if record.exc_info:
                exc = "".join(traceback.format_exception(*record.exc_info))[:12000]
            source = getattr(record, "app_source", "app")
            payload = {
                "created_at": datetime.fromtimestamp(record.created, tz=timezone.utc),
                "level": record.levelname,
                "logger_name": record.name[:255],
                "message": message,
                "exception": exc,
                "source": str(source)[:32],
            }
            q = _ensure_db_worker()
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass
        except Exception:
            self.handleError(record)


def configure_logging(force: bool = False) -> LoggingOptions:
    """Apply console + optional DB handlers from runtime settings."""
    global _configured
    opts = _read_options()
    root = logging.getLogger()
    root.handlers.clear()

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(opts.console_level)
    console.setFormatter(ColoredConsoleFormatter(use_color=console_use_color()))
    root.addHandler(console)

    if opts.persist_to_db:
        db_handler = DatabaseLogHandler()
        db_handler.setLevel(opts.db_level)
        root.addHandler(db_handler)
        root.setLevel(opts.db_level)
    else:
        root.setLevel(opts.console_level)

    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True
    root.info(
        "Logging configured (level=%s, db=%s)",
        opts.level_name,
        opts.persist_to_db,
    )
    return opts


def ensure_logging_configured() -> None:
    if not _configured:
        configure_logging()
