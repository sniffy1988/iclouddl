from __future__ import annotations

import logging
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
MAX_STORED_LOGS = 5000
_db_queue: queue.Queue[dict] | None = None
_db_worker: threading.Thread | None = None
_configured = False

_QUIET_LOGGERS = ("httpx", "httpcore", "urllib3", "apscheduler", "telegram", "asyncio")


@dataclass(frozen=True)
class LoggingOptions:
    debug_enabled: bool
    persist_to_db: bool


def _read_options() -> LoggingOptions:
    try:
        from iclouddownloader.services.runtime_settings_service import get_effective_settings

        settings = get_effective_settings()
        enabled = bool(getattr(settings, "debug_logging_enabled", False))
        return LoggingOptions(debug_enabled=enabled, persist_to_db=enabled)
    except Exception:
        return LoggingOptions(debug_enabled=False, persist_to_db=False)


def is_debug_logging_enabled() -> bool:
    return _read_options().debug_enabled


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


class DatabaseLogHandler(logging.Handler):
    """Async queue writer; only emits when debug logging is enabled in settings."""

    def emit(self, record: LogRecord) -> None:
        if not _read_options().persist_to_db:
            return
        if record.levelno < logging.INFO and not _read_options().debug_enabled:
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

    console_level = logging.DEBUG if opts.debug_enabled else logging.INFO
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(console)

    if opts.persist_to_db:
        db_handler = DatabaseLogHandler()
        db_handler.setLevel(logging.DEBUG if opts.debug_enabled else logging.INFO)
        root.addHandler(db_handler)

    root.setLevel(logging.DEBUG if opts.debug_enabled else logging.INFO)

    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True
    root.info(
        "Logging configured (debug=%s, db=%s)",
        opts.debug_enabled,
        opts.persist_to_db,
    )
    return opts


def ensure_logging_configured() -> None:
    if not _configured:
        configure_logging()
