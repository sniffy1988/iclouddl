"""iCloud asset media classification and multi-part downloads."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def is_stale_download_url_error(exc: BaseException) -> bool:
    """True when Apple's signed download URL expired (HTTP 410 Gone)."""
    try:
        from pyicloud.exceptions import PyiCloudAPIResponseException
    except ImportError:
        return False
    if not isinstance(exc, PyiCloudAPIResponseException):
        return False
    code = exc.code
    if code in (410, "410"):
        return True
    return "gone" in (exc.reason or "").lower()

LIVE_VIDEO_PREFIX = "resOriginalVidCompl"
RAW_EXTENSIONS = ("cr2", "cr3", "nef", "arw", "dng", "orf", "rw2", "raw")


def _coerce_field_entry(entry: Any) -> dict:
    if isinstance(entry, dict):
        return entry
    if hasattr(entry, "model_dump"):
        return entry.model_dump(mode="python")
    value = getattr(entry, "value", None)
    if value is not None and hasattr(value, "model_dump"):
        value = value.model_dump(mode="python")
    field_type = getattr(entry, "type", None)
    if value is not None or field_type is not None:
        return {"type": field_type, "value": value}
    return {}


def _coerce_field_map(fields: Any) -> dict[str, dict]:
    if not fields:
        return {}
    if not isinstance(fields, dict):
        if hasattr(fields, "model_dump"):
            fields = fields.model_dump(mode="python").get("fields") or {}
        else:
            return {}
    return {key: _coerce_field_entry(entry) for key, entry in fields.items()}


def master_fields(photo: Any) -> dict[str, dict]:
    """Return CloudKit field map (dict or pyicloud CKRecord)."""
    record = getattr(photo, "_master_record", None)
    if record is None:
        return {}
    if isinstance(record, dict):
        raw = record.get("fields", record)
        return _coerce_field_map(raw)
    raw = getattr(record, "fields", None)
    return _coerce_field_map(raw)


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


def _entry_value(entry: dict | None) -> Any:
    if not entry:
        return None
    return entry.get("value")


def _field_value(fields: dict, key: str) -> str | None:
    val = _entry_value(fields.get(key))
    return str(val) if val is not None else None


def _download_url(fields: dict, prefix: str) -> str | None:
    res_key = f"{prefix}Res"
    value = _entry_value(fields.get(res_key))
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("downloadURL")
    return getattr(value, "downloadURL", None)


def download_version(photo: Any, version: str = "original") -> Any:
    return photo.download(version)


# Prefixes aligned with pyicloud PhotoAsset.PHOTO_VERSION_LOOKUP / VIDEO_VERSION_LOOKUP.
_VERSION_PREFIX = {
    "original": "resOriginal",
    "medium": "resJPEGMed",
    "alternative": "resOriginalAlt",
    "thumb": "resJPEGThumb",
}


def _album_for_photo(photo: Any) -> Any | None:
    """Resolve the All Photos album used to refresh stale CloudKit URLs."""
    library = getattr(photo, "_library", None)
    service = getattr(photo, "_service", None)
    if service is None and library is not None:
        service = getattr(library, "service", library)
    if service is None:
        return None
    photos_root = getattr(service, "photos", None)
    if photos_root is None:
        return None
    albums = getattr(photos_root, "albums", None)
    if albums is not None:
        album = albums.get("All Photos")
        if album is not None:
            return album
    return getattr(photos_root, "all", None)


def clear_photo_resource_cache(photo: Any) -> None:
    if hasattr(photo, "_resources"):
        photo._resources = None


def refresh_photo_asset(photo: Any) -> bool:
    """Re-query CloudKit for this asset so download URLs are fresh (long syncs expire URLs)."""
    photo_id = getattr(photo, "id", None) or getattr(photo, "asset_id", None)
    if not photo_id:
        return False
    album = _album_for_photo(photo)
    if album is None or not hasattr(album, "_get_photo"):
        return False
    try:
        fresh = album._get_photo(str(photo_id))
    except Exception:
        logger.warning("Could not refresh iCloud asset %s", photo_id, exc_info=True)
        return False
    photo._master_record = fresh._master_record
    photo._asset_record = getattr(fresh, "_asset_record", getattr(photo, "_asset_record", None))
    clear_photo_resource_cache(photo)
    return True


def _write_response(response: Any, dest: Path) -> None:
    if hasattr(response, "raw"):
        with dest.open("wb") as f:
            shutil.copyfileobj(response.raw, f)
    elif hasattr(response, "read"):
        with dest.open("wb") as f:
            shutil.copyfileobj(response, f)
    else:
        with dest.open("wb") as f:
            f.write(response)


def _stream_url_to_file(service: Any, url: str, dest: Path) -> None:
    response = service.session.get(url, stream=True)
    response.raise_for_status()
    with dest.open("wb") as f:
        shutil.copyfileobj(response.raw, f)


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
    _stream_url_to_file(service, url, dest)
    return True


def _download_via_prefix_or_url(photo: Any, dest: Path, version: str) -> bool:
    prefix = _VERSION_PREFIX.get(version, "resOriginal")
    if download_by_prefix(photo, prefix, dest):
        return True
    download_url_fn = getattr(photo, "download_url", None)
    url = download_url_fn(version) if callable(download_url_fn) else None
    if not url:
        return False
    service = getattr(photo, "_service", None)
    if not service:
        raise ValueError("Photo asset has no _service for download")
    _stream_url_to_file(service, url, dest)
    return True


def _download_via_pyicloud_bytes(photo: Any, dest: Path, version: str) -> bool:
    data = download_version(photo, version)
    if isinstance(data, bytes):
        if not data:
            raise ValueError(f"Empty download payload (version={version})")
        dest.write_bytes(data)
        return True
    if data is not None:
        _write_response(data, dest)
        return True
    return False


def download_asset_to_file(
    photo: Any,
    dest: Path,
    version: str = "original",
    *,
    _retried: bool = False,
) -> None:
    """Write one iCloud asset to disk; refresh CloudKit URLs once on HTTP 410 Gone."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if _download_via_prefix_or_url(photo, dest, version):
            return
        if _download_via_pyicloud_bytes(photo, dest, version):
            return
        raise ValueError(f"Download returned no data (version={version})")
    except Exception as exc:
        if _retried or not is_stale_download_url_error(exc):
            raise
        asset_id = getattr(photo, "id", None) or getattr(photo, "asset_id", "unknown")
        if refresh_photo_asset(photo):
            logger.info("Refreshed expired download URL for asset %s; retrying", asset_id)
            download_asset_to_file(photo, dest, version=version, _retried=True)
            return
        raise


def live_video_filename(primary_filename: str, fields: dict | None = None) -> str:
    stem = Path(primary_filename).stem
    file_type = _field_value(fields or {}, f"{LIVE_VIDEO_PREFIX}FileType")
    if file_type:
        ft = file_type.lower()
        if "quicktime" in ft or ft.endswith("movie") or ft.endswith(".mov"):
            ext = "mov"
        elif "/" in ft:
            ext = ft.split("/")[-1]
            if ext in ("quicktime", "movie"):
                ext = "mov"
        else:
            ext = ft.rsplit(".", 1)[-1]
        return f"{stem}.{ext}"
    return f"{stem}.mov"
