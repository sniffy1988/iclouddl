from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from iclouddownloader.api.deps import get_db, require_auth
from iclouddownloader.api.schemas import DashboardStats, SyncRunResponse
from iclouddownloader.db.models import SyncRunStatus
from iclouddownloader.jobs.queue import enqueue_sync
from iclouddownloader.services.sync_service import SyncInProgressError, SyncService
from iclouddownloader.services.user_service import UserService

router = APIRouter(tags=["sync"])


@router.get("/api/sync-runs", response_model=list[SyncRunResponse])
def list_sync_runs(
    user_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    run_status = SyncRunStatus(status) if status else None
    return SyncService(db).list_sync_runs(user_id=user_id, status=run_status, limit=limit, offset=offset)


@router.get("/api/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    return SyncService(db).dashboard_stats()


@router.post("/api/sync/trigger-due")
def trigger_due_syncs(
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Manually trigger sync for all enabled users that are due."""
    sync_svc = SyncService(db)
    user_svc = UserService(db)
    queued: list[int] = []
    skipped: list[int] = []

    for user in user_svc.users_due_for_sync():
        try:
            sync_svc.ensure_can_start_sync(user.id)
            sync_svc.mark_sync_queued(user.id)
            queued.append(user.id)
        except SyncInProgressError:
            skipped.append(user.id)

    for uid in queued:
        enqueue_sync(uid)

    return {
        "ok": True,
        "queued": queued,
        "skipped_already_running": skipped,
        "message": f"Started {len(queued)} sync job(s)",
    }
