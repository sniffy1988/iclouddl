from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, wait

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import PhotoSource, SyncRun, SyncRunScope, SyncRunStatus


def run_matches_cancel_scope(run: SyncRun, source: PhotoSource | None) -> bool:
    if source is None:
        return True
    requested = SyncRunScope.icloud if source == PhotoSource.icloud else SyncRunScope.google_photos
    if run.scope == SyncRunScope.all:
        return True
    return run.scope == requested


def is_sync_cancel_requested(db: Session, sync_run_id: int | None) -> bool:
    if sync_run_id is None:
        return False
    db.expire_all()
    return bool(
        db.scalar(
            select(SyncRun.cancel_requested).where(
                SyncRun.id == sync_run_id,
                SyncRun.status == SyncRunStatus.running,
            )
        )
    )


def drain_futures_with_cancel(
    db: Session,
    sync_run_id: int | None,
    futures: dict[Future, object],
    *,
    on_progress=None,
) -> bool:
    """Wait for futures; return True if stopped due to cancel request."""
    pending = set(futures.keys())
    while pending:
        if is_sync_cancel_requested(db, sync_run_id):
            for future in pending:
                future.cancel()
            return True
        done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
        for future in done:
            try:
                future.result()
            except Exception:
                pass
            if on_progress:
                on_progress()
    return False
