from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from iclouddownloader.config import get_settings
from iclouddownloader.db.models import User
from iclouddownloader.google.oauth import (
    build_authorize_url,
    exchange_code,
    fetch_user_email,
    parse_oauth_state,
    revoke_token,
)
from iclouddownloader.secrets.token_cipher import TokenEncryptionNotConfigured, encrypt_refresh_token

logger = logging.getLogger(__name__)


class GoogleAuthService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def is_authorized(user: User) -> bool:
        return bool(
            user.google_refresh_token_encrypted
            and not user.google_needs_auth
            and user.google_authenticated_at
        )

    @staticmethod
    def google_auth_status(user: User) -> str:
        if not user.google_account_email and not user.google_refresh_token_encrypted:
            return "not_linked"
        if GoogleAuthService.is_authorized(user):
            return "authorized"
        if user.google_needs_auth:
            return "reauth_required"
        return "not_authorized"

    @staticmethod
    def redirect_uri_static(public_base_url: str | None = None) -> str:
        base = (public_base_url or get_settings().web_public_base_url).rstrip("/")
        return f"{base}/api/auth/google/callback"

    def redirect_uri(self) -> str:
        return self.redirect_uri_static()

    def start_oauth(self, user_id: int) -> dict[str, str]:
        user = self.db.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        url, _state = build_authorize_url(user_id, self.redirect_uri())
        return {"authorize_url": url}

    def complete_oauth(self, code: str, state: str) -> User:
        user_id = parse_oauth_state(state)
        user = self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found for OAuth state")

        tokens = exchange_code(code, self.redirect_uri())
        refresh = tokens.get("refresh_token")
        if not refresh:
            raise ValueError("Google did not return a refresh token; revoke app access and try again")

        access = tokens.get("access_token", "")
        email = fetch_user_email(access) if access else None

        try:
            encrypted = encrypt_refresh_token(refresh)
        except TokenEncryptionNotConfigured as e:
            raise ValueError(str(e)) from e

        user.google_refresh_token_encrypted = encrypted
        user.google_account_email = email
        user.google_authenticated_at = datetime.now(timezone.utc)
        user.google_needs_auth = False
        if not user.display_name and email:
            user.display_name = email
        self.db.commit()
        self.db.refresh(user)
        return user

    def disconnect(self, user: User) -> None:
        if user.google_refresh_token_encrypted:
            try:
                from iclouddownloader.secrets.token_cipher import decrypt_refresh_token

                token = decrypt_refresh_token(user.google_refresh_token_encrypted)
                revoke_token(token)
            except Exception:
                logger.warning("Could not revoke Google token for user %s", user.id)
        user.google_refresh_token_encrypted = None
        user.google_account_email = None
        user.google_authenticated_at = None
        user.google_needs_auth = True
        self.db.commit()
