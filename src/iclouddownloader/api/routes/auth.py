from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from iclouddownloader.api.deps import SESSION_COOKIE, create_session, get_db, require_auth, verify_admin_password
from iclouddownloader.api.schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    if not verify_admin_password(body.password):
        from fastapi import HTTPException, status

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
