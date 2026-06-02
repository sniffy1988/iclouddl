from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from iclouddownloader.api.deps import get_db, require_auth
from iclouddownloader.api.schemas import AppLogEntry, AppLogListResponse
from iclouddownloader.services.log_service import LogService

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=AppLogListResponse)
def list_logs(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    level: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    rows, total = LogService(db).list_logs(limit=limit, offset=offset, level=level, search=search)
    return AppLogListResponse(
        items=[AppLogEntry(**LogService.serialize(r)) for r in rows],
        total=total,
    )


@router.delete("")
def clear_logs(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    deleted = LogService(db).clear_logs()
    return {"ok": True, "deleted": deleted}
