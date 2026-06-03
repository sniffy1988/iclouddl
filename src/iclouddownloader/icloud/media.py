"""iCloud asset media classification and multi-part downloads."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LIVE_VIDEO_PREFIX = "resOriginalVidCompl"
RAW_EXTENSIONS = ("cr2", "cr3", "nef", "arw", "dng", "orf", "rw2", "raw")


def master_fields(photo: Any) -> dict:
    record = getattr(photo, "_master_record", None) or {}
    return record.get("fields") or {}


def is_video_asset(photo: Any) -> bool:
    return "resVidSmallRes" in master_fields(photo)


def has_live_video_component(photo: Any) -> bool:
    return f"{LIVE_VIDEO_PREFIX}Res" in master_fields(photo)


def classify_media_type(photo: Any) -> str:
    if is_video_asset(photo):
        return "video"
    if has_live_video_component(photo):
        return "live_photo"
    file_type = _field_value(master_fields(photo), "resOriginalFileType")
    if file_type:
        ft = str(file_type).lower()
        if "raw" in ft or any(ft.endswith(ext) for ext in RAW_EXTENSIONS):
            return "raw"
    return "photo"


def _field_value(fields: dict, key: str) -> str | None:
    entry = fields.get(key)
    if not entry:
        return None
    val = entry.get("value")
    return str(val) if val is not None else None


def _download_url(fields: dict, prefix: str) -> str | None:
    res_key = f"{prefix}Res"
    entry = fields.get(res_key)
    if not entry:
        return None
    value = entry.get("value") or {}
    return value.get("downloadURL")


def download_version(photo: Any, version: str = "original") -> Any:
    return photo.download(version)


def download_by_prefix(photo: Any, prefix: str, dest: Path) -> bool:
    """Download a specific iCloud resource prefix (e.g. live photo video)."""
    fields = master_fields(photo)
    url = _download_url(fields, prefix)
    if not url:
        return False
    service = getattr(photo, "_service", None)
    if not service:
        logger.warning("Photo asset has no _service; cannot download %s", prefix)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = service.session.get(url, stream=True)
    response.raise_for_status()
    with dest.open("wb") as f:
        shutil.copyfileobj(response.raw, f)
    return True


def live_video_filename(primary_filename: str, fields: dict | None = None) -> str:
    stem = Path(primary_filename).stem
    file_type = _field_value(fields or {}, f"{LIVE_VIDEO_PREFIX}FileType")
    if file_type:
        ext = file_type.lower().split("/")[-1]
        if ext in ("quicktime", "movie"):
            ext = "mov"
        return f"{stem}.{ext}"
    return f"{stem}.mov"
