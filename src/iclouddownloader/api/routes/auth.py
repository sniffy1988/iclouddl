from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from iclouddownloader.admin_auth import admin_configured, set_admin_password, verify_admin_password
from iclouddownloader.api.deps import (
    SESSION_COOKIE,
    create_session,
    get_db,
    get_session_token,
    require_auth,
    session_valid,
)
from iclouddownloader.api.schemas import AuthStatusResponse, LoginRequest, SetupAdminRequest
from iclouddownloader.db.models import RuntimeSettings
from iclouddownloader.services.runtime_settings_service import RuntimeSettingsService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _runtime_row(db: Session) -> RuntimeSettings:
    return RuntimeSettingsService(db).get_row()


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(
    db: Session = Depends(get_db),
    token: str | None = Depends(get_session_token),
):
    row = db.get(RuntimeSettings, 1)
    needs_setup = not admin_configured(row)
    authenticated = False if needs_setup else session_valid(db, token)
    return AuthStatusResponse(needs_setup=needs_setup, authenticated=authenticated)


@router.post("/setup")
def setup_admin(
    body: SetupAdminRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    row = _runtime_row(db)
    if admin_configured(row):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account already exists",
        )
    set_admin_password(db, row, body.password)
    token = create_session(db)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return {"ok": True}


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    row = db.get(RuntimeSettings, 1)
    if not admin_configured(row):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No admin account — create one on the setup screen first",
        )
    if not verify_admin_password(body.password, row):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    token = create_session(db)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, _: None = Depends(require_auth)):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/me")
def me(_: None = Depends(require_auth)):
    return {"authenticated": True}
