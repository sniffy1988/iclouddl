from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import Photo, PhotoSource, PhotoStatus, SyncCursor, User
from iclouddownloader.google.client import GooglePhotosClient

GOOGLE_LIBRARY_KEY = "google_photos"

logger = logging.getLogger(__name__)


def _parse_creation_time(item: dict[str, Any]) -> datetime | None:
    meta = item.get("mediaMetadata") or {}
    raw = meta.get("creationTime")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _filename(item: dict[str, Any]) -> str:
    return str(item.get("filename") or f"{item.get('id', 'unknown')}.jpg")


def is_motion_photo(item: dict[str, Any]) -> bool:
    meta = item.get("mediaMetadata") or {}
    photo_meta = meta.get("photo") or {}
    return bool(photo_meta.get("motionPhoto"))


def media_item_ready(item: dict[str, Any]) -> bool:
    meta = item.get("mediaMetadata") or {}
    status = meta.get("status")
    return status is None or status == "READY"


def _media_type(item: dict[str, Any]) -> str | None:
    meta = item.get("mediaMetadata") or {}
    if meta.get("video"):
        return "video"
    if is_motion_photo(item):
        return "motion_photo"
    if meta.get("photo"):
        return "photo"
    return None


def upsert_google_photo(db: Session, user_id: int, item: dict[str, Any]) -> str:
    aid = str(item["id"])
    existing = db.scalar(
        select(Photo).where(
            Photo.user_id == user_id,
            Photo.source == PhotoSource.google_photos,
            Photo.provider_asset_id == aid,
        )
    )
    filename = _filename(item)
    date = _parse_creation_time(item)
    media = _media_type(item)

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
        source=PhotoSource.google_photos,
        provider_asset_id=aid,
        filename=filename,
        status=PhotoStatus.pending,
        asset_date=date,
        media_type=media,
    )
    db.add(record)
    return "created"


def _get_or_create_cursor(db: Session, user: User) -> SyncCursor:
    cursor = db.scalar(
        select(SyncCursor).where(
            SyncCursor.user_id == user.id,
            SyncCursor.library_key == GOOGLE_LIBRARY_KEY,
        )
    )
    if not cursor:
        cursor = SyncCursor(user_id=user.id, library_key=GOOGLE_LIBRARY_KEY)
        db.add(cursor)
        db.flush()
    return cursor


def index_google_library_to_db(
    db: Session,
    user: User,
    *,
    commit_every: int = 200,
    on_progress: Callable[[dict[str, int]], None] | None = None,
) -> dict[str, int]:
    client = GooglePhotosClient.for_user(user)
    cursor = _get_or_create_cursor(db, user)
    stats = {"indexed": 0, "created": 0, "updated": 0}
    pending_commit = 0
    page_token = cursor.cursor_value or None

    while True:
        data = client.list_media_items(page_size=100, page_token=page_token)
        for item in data.get("mediaItems") or []:
            action = upsert_google_photo(db, user.id, item)
            stats["indexed"] += 1
            stats[action] += 1
            pending_commit += 1
            if pending_commit >= commit_every:
                db.commit()
                pending_commit = 0
                if on_progress:
                    on_progress(dict(stats))

        page_token = data.get("nextPageToken")
        cursor.cursor_value = page_token
        db.commit()
        if on_progress:
            on_progress(dict(stats))
        if not page_token:
            break

    if on_progress:
        on_progress(dict(stats))
    logger.info(
        "Google Photos index complete for user %s: %s mediaItems (full library, no type filter)",
        user.id,
        stats["indexed"],
    )
    return stats
