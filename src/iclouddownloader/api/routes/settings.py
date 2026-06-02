import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from iclouddownloader.api.deps import get_db, require_auth
from iclouddownloader.api.schemas import ImmichTestRequest, SettingsResponse, SettingsUpdate
from iclouddownloader.integrations.immich import ImmichClient
from iclouddownloader.path_template import validate_path_template
from iclouddownloader.services.runtime_settings_service import RuntimeSettingsService
from iclouddownloader.notifications import AppNotifier

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=SettingsResponse)
def get_settings_view(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    return SettingsResponse(**RuntimeSettingsService(db).to_api_dict())


@router.patch("/settings", response_model=SettingsResponse)
def update_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    svc = RuntimeSettingsService(db)
    data = body.model_dump(exclude_unset=True)
    if "download_path_template" in data and data["download_path_template"] is not None:
        try:
            validate_path_template(data["download_path_template"])
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    try:
        svc.update(data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return SettingsResponse(**svc.to_api_dict())


@router.post("/telegram/test")
async def test_telegram(db: Session = Depends(get_db), _: None = Depends(require_auth)):
    RuntimeSettingsService(db).get_row()
    notifier = AppNotifier()
    ok = await notifier.test_telegram()
    return {"ok": ok}


@router.get("/immich/libraries")
def list_immich_libraries(_: None = Depends(require_auth)):
    ok, result = ImmichClient().list_libraries()
    if not ok:
        raise HTTPException(400, str(result))
    return {"libraries": result}


@router.post("/immich/test")
async def test_immich(
    body: ImmichTestRequest | None = None,
    _: None = Depends(require_auth),
):
    library_id = body.library_id if body else None
    ok, message = await ImmichClient().test_connection(library_id)
    return {"ok": ok, "message": message}


