import json
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from iclouddownloader.api.deps import get_db, require_auth
from iclouddownloader.api.schemas import DashboardStats, SyncRunResponse
from iclouddownloader.db.models import SyncRunStatus
from iclouddownloader.events import get_event_bus
from iclouddownloader.services.sync_service import SyncInProgressError, SyncService
from iclouddownloader.services.user_service import UserService
from iclouddownloader.notifications import AppNotifier

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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Manually trigger sync for all enabled users that are due."""
    sync_svc = SyncService(db)
    user_svc = UserService(db)
    notifier = AppNotifier()
    queued: list[int] = []
    skipped: list[int] = []

    for user in user_svc.users_due_for_sync():
        try:
            sync_svc.ensure_can_start_sync(user.id)
            sync_svc.mark_sync_queued(user.id)
            queued.append(user.id)
        except SyncInProgressError:
            skipped.append(user.id)

    def _run(uid: int):
        from iclouddownloader.db.session import get_session_factory

        sdb = get_session_factory()()
        try:
            SyncService(sdb, notifier=notifier).trigger_sync(uid)
        finally:
            sdb.close()

    for uid in queued:
        background_tasks.add_task(_run, uid)

    return {
        "ok": True,
        "queued": queued,
        "skipped_already_running": skipped,
        "message": f"Started {len(queued)} sync job(s)",
    }


@router.get("/api/events/sync")
async def sync_events(_: None = Depends(require_auth)):
    bus = get_event_bus()

    async def generator():
        async for event in bus.subscribe():
            yield {"event": event.type, "data": json.dumps(asdict(event))}

    return EventSourceResponse(generator())
