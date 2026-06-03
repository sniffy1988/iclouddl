from __future__ import annotations

import logging
from typing import Any, Iterator

logger = logging.getLogger(__name__)


def get_all_photos_album(api) -> Any:
    return api.photos.albums.get("All Photos") or api.photos.all


def iter_library_photos(api) -> Iterator[Any]:
    try:
        album = get_all_photos_album(api)
        yield from album
    except Exception:
        logger.exception("Failed to iterate iCloud photos")
        return


def count_library_photos(api) -> int:
    """Count by iterating the library (same walk as DB indexing)."""
    count = 0
    for _ in iter_library_photos(api):
        count += 1
        if count % 500 == 0:
            logger.info("Counted %s photos so far…", count)
    return count


def list_library_photos(api) -> list[Any]:
    photos = list(iter_library_photos(api))
    logger.info(
        "iCloud library walk complete: %s assets from All Photos (no type filter)",
        len(photos),
    )
    return photos
