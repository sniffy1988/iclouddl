from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import Photo, PhotoSource, PhotoStatus, User
from iclouddownloader.icloud.library import iter_library_photos

logger = logging.getLogger(__name__)


def asset_id(photo: Any) -> str:
    return str(getattr(photo, "id", None) or getattr(photo, "filename", "unknown"))


def asset_filename(photo: Any) -> str:
    return getattr(photo, "filename", "unknown.jpg")


def asset_date(photo: Any) -> datetime | None:
    for attr in ("created", "added_date", "asset_date"):
        val = getattr(photo, attr, None)
        if val is None:
            continue
        if isinstance(val, datetime):
            return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def asset_media_type(photo: Any) -> str | None:
    from iclouddownloader.icloud.media import classify_media_type

    try:
        return classify_media_type(photo)
    except Exception:
        return getattr(photo, "media_type", None)


def upsert_photo_record(
    db: Session,
    user_id: int,
    api_photo: Any,
) -> str:
    """Insert or update a photo row from iCloud metadata (no download)."""
    aid = asset_id(api_photo)
    existing = db.scalar(
        select(Photo).where(
            Photo.user_id == user_id,
            Photo.source == PhotoSource.icloud,
            Photo.provider_asset_id == aid,
        )
    )
    filename = asset_filename(api_photo)
    date = asset_date(api_photo)
    media = asset_media_type(api_photo)

    if existing:
        if existing.status != PhotoStatus.downloaded:
            existing.filename = filename
            existing.asset_date = date
            existing.media_type = media
            if existing.status == PhotoStatus.failed:
                existing.error_message = None
        return "updated"

    record = Photo(
        user_id=user_id,
        source=PhotoSource.icloud,
        provider_asset_id=aid,
        filename=filename,
        status=PhotoStatus.pending,
        asset_date=date,
        media_type=media,
    )
    db.add(record)
    return "created"


def index_library_to_db(
    db: Session,
    user: User,
    api: Any,
    *,
    commit_every: int = 200,
    progress_every: int = 10,
    on_progress: Callable[[dict[str, int]], None] | None = None,
) -> dict[str, int]:
    """Walk iCloud library and fill ``photos`` table (metadata only)."""
    stats = {"indexed": 0, "created": 0, "updated": 0}
    pending_commit = 0

    def _maybe_report_progress() -> None:
        if not on_progress:
            return
        if stats["indexed"] == 1 or stats["indexed"] % progress_every == 0:
            on_progress(dict(stats))

    for api_photo in iter_library_photos(api):
        action = upsert_photo_record(db, user.id, api_photo)
        stats["indexed"] += 1
        stats[action] += 1
        pending_commit += 1
        _maybe_report_progress()

        if pending_commit >= commit_every:
            db.commit()
            pending_commit = 0

    db.commit()
    if on_progress:
        on_progress(dict(stats))
    logger.info(
        "iCloud index complete for user %s: %s assets (full All Photos library)",
        user.id,
        stats["indexed"],
    )
    return stats
