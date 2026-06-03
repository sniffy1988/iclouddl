"""Verify photos marked downloaded still exist on disk (user may delete files)."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import Photo, PhotoSource, PhotoStatus

logger = logging.getLogger(__name__)

ChecksumFn = Callable[[Path], str]


def default_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def path_is_present(path: str | None, *, min_size: int = 1) -> bool:
    if not path:
        return False
    try:
        p = Path(path)
        return p.is_file() and p.stat().st_size >= min_size
    except OSError:
        return False


def photo_files_on_disk(
    record: Photo,
    *,
    require_companion: bool = False,
) -> bool:
    """True when primary file exists; companion required only if flag or DB path set."""
    if not path_is_present(record.local_path):
        return False
    needs_companion = require_companion or bool(record.companion_local_path)
    if needs_companion and not path_is_present(record.companion_local_path):
        return False
    return True


def mark_photo_missing_on_disk(
    record: Photo,
    *,
    reason: str = "Local file missing (deleted or moved)",
) -> bool:
    """Reset a downloaded row to pending so sync will fetch again. Returns True if changed."""
    if record.status != PhotoStatus.downloaded:
        return False
    record.status = PhotoStatus.pending
    record.local_path = None
    record.file_size = None
    record.checksum_sha256 = None
    record.companion_local_path = None
    record.companion_media_type = None
    record.companion_file_size = None
    record.companion_checksum_sha256 = None
    record.downloaded_at = None
    record.error_message = reason
    return True


def verify_written_file(path: Path, *, min_size: int = 1) -> None:
    if not path_is_present(str(path), min_size=min_size):
        raise ValueError(f"Download did not create a file on disk: {path}")


def _resolve_existing_path(expected: Path | None, stored: str | None) -> Path | None:
    for candidate in (expected, Path(stored) if stored else None):
        if candidate is not None and path_is_present(str(candidate)):
            return candidate.resolve()
    return None


def try_adopt_existing_on_disk(
    record: Photo,
    primary: Path,
    *,
    companion: Path | None = None,
    require_companion: bool = False,
    companion_media_type: str | None = None,
    checksum_fn: ChecksumFn | None = None,
) -> bool:
    """Mark the photo downloaded when files already exist at expected paths (skip re-download)."""
    checksum = checksum_fn or default_checksum
    needs_companion = require_companion or bool(record.companion_local_path)

    primary_path = _resolve_existing_path(primary, record.local_path)
    if not primary_path:
        return False

    companion_path: Path | None = None
    if needs_companion:
        companion_path = _resolve_existing_path(companion, record.companion_local_path)
        if not companion_path:
            return False

    path_changed = record.local_path != str(primary_path)
    record.local_path = str(primary_path)
    record.file_size = primary_path.stat().st_size
    if not record.checksum_sha256 or path_changed:
        record.checksum_sha256 = checksum(primary_path)

    if companion_path:
        record.companion_local_path = str(companion_path)
        record.companion_file_size = companion_path.stat().st_size
        if companion_media_type:
            record.companion_media_type = companion_media_type
        if not record.companion_checksum_sha256:
            record.companion_checksum_sha256 = checksum(companion_path)
    else:
        record.companion_local_path = None
        record.companion_media_type = None
        record.companion_file_size = None
        record.companion_checksum_sha256 = None

    record.status = PhotoStatus.downloaded
    record.downloaded_at = record.downloaded_at or datetime.now(timezone.utc)
    record.error_message = None
    return True


def reconcile_stale_downloads(
    db: Session,
    user_id: int,
    source: PhotoSource | None = None,
) -> int:
    """Mark downloaded photos as pending when local files are gone. Returns rows updated."""
    stmt = select(Photo).where(
        Photo.user_id == user_id,
        Photo.status == PhotoStatus.downloaded,
    )
    if source is not None:
        stmt = stmt.where(Photo.source == source)

    reset = 0
    for record in db.scalars(stmt):
        if photo_files_on_disk(record, require_companion=bool(record.companion_local_path)):
            continue
        if mark_photo_missing_on_disk(record):
            reset += 1

    if reset:
        label = source.value if source else "all"
        logger.info(
            "Reconciled %s missing local file(s) for user %s (%s)",
            reset,
            user_id,
            label,
        )
    return reset
