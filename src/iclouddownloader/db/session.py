from collections.abc import Generator
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from iclouddownloader.config import get_settings

_engine = None
_SessionLocal = None


def sqlite_file_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite"):
        return None
    parsed = urlparse(database_url)
    if parsed.path in ("", "/"):
        return None
    # sqlite:////absolute/path → path is /absolute/path
    # sqlite:///./relative → ./relative
    raw = unquote(parsed.path.lstrip("/"))
    if database_url.startswith("sqlite:////"):
        return Path("/" + raw)
    return Path(raw)


def ensure_sqlite_parent_dir(database_url: str) -> None:
    db_path = sqlite_file_path(database_url)
    if db_path:
        db_path.parent.mkdir(parents=True, exist_ok=True)


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        kwargs: dict = {"pool_pre_ping": True}
        if settings.database_url.startswith("sqlite"):
            ensure_sqlite_parent_dir(settings.database_url)
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, **kwargs)
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
