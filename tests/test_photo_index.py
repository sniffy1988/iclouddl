import os
import tempfile
from unittest.mock import patch

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite://"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from iclouddownloader.db.models import Base, Photo, PhotoStatus, User
from iclouddownloader.icloud.assets import index_library_to_db

import iclouddownloader.db.session as session_mod

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
session_mod._engine = _test_engine
session_mod._SessionLocal = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)
Base.metadata.create_all(_test_engine)


def _make_photo(pid: str, name: str):
    from unittest.mock import MagicMock

    p = MagicMock()
    p.id = pid
    p.filename = name
    p.configure_mock(created=None, added_date=None, asset_date=None, media_type="image")
    return p


def test_index_library_to_db():
    db = session_mod._SessionLocal()
    user = User(apple_id="idx@test.com", download_dir=_tmp, sync_interval_seconds=3600)
    db.add(user)
    db.commit()

    photos = [_make_photo("a1", "one.jpg"), _make_photo("a2", "two.jpg")]

    with patch(
        "iclouddownloader.icloud.assets.iter_library_photos",
        return_value=iter(photos),
    ):
        stats = index_library_to_db(db, user, api=None)

    assert stats["indexed"] == 2
    assert stats["created"] == 2
    from sqlalchemy import select

    rows = list(db.scalars(select(Photo).where(Photo.user_id == user.id)).all())
    assert len(rows) == 2
    assert all(r.status == PhotoStatus.pending for r in rows)
