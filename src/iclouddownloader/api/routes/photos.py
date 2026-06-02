from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from iclouddownloader.api.deps import get_db, require_auth
from iclouddownloader.api.schemas import PhotoResponse
from iclouddownloader.db.models import PhotoStatus
from iclouddownloader.services.sync_service import SyncService

router = APIRouter(prefix="/api/users", tags=["photos"])


@router.get("/{user_id}/photos", response_model=list[PhotoResponse])
def list_photos(
    user_id: int,
    status: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    photo_status = PhotoStatus(status) if status else None
    return SyncService(db).list_photos(user_id, status=photo_status, limit=limit, offset=offset)
