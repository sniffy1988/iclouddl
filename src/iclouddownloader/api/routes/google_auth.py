from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from iclouddownloader.api.deps import get_db, require_auth
from iclouddownloader.config import get_settings
from iclouddownloader.services.google_auth_service import GoogleAuthService
from iclouddownloader.services.user_service import UserService

router = APIRouter(prefix="/api", tags=["google-auth"])


@router.post("/users/{user_id}/auth/google/start")
def start_google_oauth(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    try:
        return GoogleAuthService(db).start_oauth(user_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/auth/google/callback")
def google_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    base = get_settings().web_public_base_url.rstrip("/")
    if error or not code or not state:
        return RedirectResponse(
            url=f"{base}/users?google=error&message={error or 'cancelled'}",
            status_code=302,
        )
    try:
        user = GoogleAuthService(db).complete_oauth(code, state)
        return RedirectResponse(
            url=f"{base}/users/{user.id}?google=connected",
            status_code=302,
        )
    except Exception as e:
        return RedirectResponse(
            url=f"{base}/users?google=error&message={str(e)[:200]}",
            status_code=302,
        )


@router.post("/users/{user_id}/auth/google/disconnect")
def disconnect_google(
    user_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    user = UserService(db).get_user(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    GoogleAuthService(db).disconnect(user)
    return {"ok": True}
