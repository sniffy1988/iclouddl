"""Live sync progress events for WebSocket / UI updates."""

from __future__ import annotations

from sqlalchemy.orm import Session

from iclouddownloader.db.models import PhotoSource, SyncRun, User
from iclouddownloader.events import SyncEvent, get_event_bus
from iclouddownloader.providers.base import account_label


def should_report_sync_progress(done: int) -> bool:
    return done == 1 or done % 10 == 0


def publish_sync_progress(
    db: Session,
    user: User,
    sync_run_id: int | None,
    counters: dict[str, int],
    *,
    source: PhotoSource,
) -> None:
    """Emit sync.progress with per-run counters and refreshed library/download totals."""
    sync_run = db.get(SyncRun, sync_run_id) if sync_run_id else None
    if sync_run:
        sync_run.photos_downloaded = counters.get("downloaded", 0)
        sync_run.photos_failed = counters.get("failed", 0)
        sync_run.photos_skipped = counters.get("skipped", 0)
        sync_run.photos_discovered = counters.get("discovered", 0)

    from iclouddownloader.services.sync_service import SyncService

    totals = SyncService(db).build_photo_count_result(user, reconcile=False)
    payload = {
        "downloaded": counters.get("downloaded", 0),
        "failed": counters.get("failed", 0),
        "skipped": counters.get("skipped", 0),
        "discovered": counters.get("discovered", 0),
        "downloaded_count": totals.get("downloaded_count"),
        "icloud_downloaded_count": totals.get("icloud_downloaded_count"),
        "google_downloaded_count": totals.get("google_downloaded_count"),
        "remaining_to_download": totals.get("remaining_to_download"),
        "icloud_remaining": totals.get("icloud_remaining"),
        "google_remaining": totals.get("google_remaining"),
        "icloud_photos_count": totals.get("icloud_photos_count"),
        "google_photos_count": totals.get("google_photos_count"),
    }
    get_event_bus().publish(
        SyncEvent(
            type="sync.progress",
            user_id=user.id,
            apple_id=user.apple_id,
            account_label=account_label(user),
            source=source.value,
            sync_run_id=sync_run_id,
            payload=payload,
        )
    )
    db.commit()
