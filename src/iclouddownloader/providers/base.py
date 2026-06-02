from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import PhotoSource, SyncRun, SyncRunScope, SyncRunStatus, User
from iclouddownloader.services.runtime_settings_service import get_effective_settings


@dataclass
class ProviderSyncResult:
    source: PhotoSource
    photos_discovered: int = 0
    photos_downloaded: int = 0
    photos_failed: int = 0
    photos_skipped: int = 0
    error: str | None = None
    success: bool = True
    cancelled: bool = False


def apply_provider_result_to_run(sync_run: SyncRun, result: ProviderSyncResult) -> None:
    from datetime import datetime, timezone

    sync_run.photos_discovered = result.photos_discovered
    sync_run.photos_downloaded = result.photos_downloaded
    sync_run.photos_failed = result.photos_failed
    sync_run.photos_skipped = result.photos_skipped
    sync_run.finished_at = datetime.now(timezone.utc)
    sync_run.cancel_requested = False
    if result.cancelled:
        sync_run.status = SyncRunStatus.cancelled
        sync_run.error_summary = "Stopped by user"
    elif result.success:
        sync_run.status = SyncRunStatus.completed
        sync_run.error_summary = None
    else:
        sync_run.status = SyncRunStatus.failed
        sync_run.error_summary = result.error


def account_label(user: User) -> str:
    return (
        user.display_name
        or user.apple_id
        or user.google_account_email
        or f"user-{user.id}"
    )


def linked_providers(user: User) -> list[PhotoSource]:
    providers: list[PhotoSource] = []
    if user.apple_id:
        providers.append(PhotoSource.icloud)
    if user.google_account_email or user.google_refresh_token_encrypted:
        providers.append(PhotoSource.google_photos)
    return providers


def scope_for_source(source: PhotoSource | None) -> SyncRunScope:
    if source is None:
        return SyncRunScope.all
    if source == PhotoSource.icloud:
        return SyncRunScope.icloud
    return SyncRunScope.google_photos


def sync_scope_conflicts(active: SyncRunScope, requested: SyncRunScope) -> bool:
    if active == SyncRunScope.all or requested == SyncRunScope.all:
        return True
    return active == requested


def active_sync_runs(db: Session, user_id: int) -> list[SyncRun]:
    return list(
        db.scalars(
            select(SyncRun).where(
                SyncRun.user_id == user_id,
                SyncRun.status == SyncRunStatus.running,
            )
        ).all()
    )


def max_workers_for_user(db: Session, user_id: int, for_scope: SyncRunScope) -> int:
    """Split download concurrency across overlapping sync runs for this user."""
    settings = get_effective_settings()
    cap = max(settings.max_concurrent_downloads, 1)
    running = active_sync_runs(db, user_id)
    if not running:
        return cap
    # Count logical download slots: each running job consumes at least one slot
    slots = len(running)
    if for_scope not in {r.scope for r in running}:
        slots += 1
    return max(1, cap // slots)
