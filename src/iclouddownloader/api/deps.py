from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.config import get_settings
from iclouddownloader.db.models import AdminSession
from iclouddownloader.db.session import get_db  # noqa: F401 — re-exported for routes
SESSION_COOKIE = "icd_session"


def session_valid(db: Session, token: str | None) -> bool:
    if not token:
        return False
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = db.scalar(
        select(AdminSession).where(
            AdminSession.token_hash == token_hash,
            AdminSession.expires_at > datetime.now(timezone.utc),
        )
    )
    return session is not None


def create_session(db: Session) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    settings = get_settings()
    session = AdminSession(
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.web_session_ttl_hours),
    )
    db.add(session)
    db.commit()
    return token


def get_session_token(
    icd_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> str | None:
    return icd_session


def require_auth(
    db: Session = Depends(get_db),
    token: str | None = Depends(get_session_token),
) -> None:
    if not session_valid(db, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
