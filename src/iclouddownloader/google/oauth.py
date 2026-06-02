from __future__ import annotations

import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from urllib.parse import urlencode

import httpx

from iclouddownloader.config import get_settings
from iclouddownloader.services.runtime_settings_service import get_effective_settings

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URI = "https://oauth2.googleapis.com/revoke"
PHOTOS_READONLY_SCOPE = "https://www.googleapis.com/auth/photoslibrary.readonly"
USERINFO_EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
SCOPES = [PHOTOS_READONLY_SCOPE, USERINFO_EMAIL_SCOPE, "openid"]


def _sign_state(payload: dict) -> str:
    secret = get_settings().web_session_secret.encode("utf-8")
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
    raw = urlsafe_b64encode(body).decode("ascii").rstrip("=")
    return f"{raw}.{sig}"


def _verify_state(state: str) -> dict:
    if "." not in state:
        raise ValueError("Invalid OAuth state")
    raw, sig = state.rsplit(".", 1)
    padding = "=" * (-len(raw) % 4)
    body = urlsafe_b64decode(raw + padding)
    secret = get_settings().web_session_secret.encode("utf-8")
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("Invalid OAuth state signature")
    payload = json.loads(body.decode("utf-8"))
    if payload.get("exp", 0) < time.time():
        raise ValueError("OAuth state expired")
    return payload


def build_authorize_url(user_id: int, redirect_uri: str) -> tuple[str, str]:
    settings = get_effective_settings()
    if not settings.google_oauth_client_id:
        raise ValueError("Google OAuth client ID is not configured in Settings")
    state = _sign_state({"user_id": user_id, "exp": time.time() + 600})
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URI}?{urlencode(params)}", state


def parse_oauth_state(state: str) -> int:
    payload = _verify_state(state)
    return int(payload["user_id"])


def exchange_code(code: str, redirect_uri: str) -> dict:
    settings = get_effective_settings()
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise ValueError("Google OAuth client credentials are not configured in Settings")
    data = {
        "code": code,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(GOOGLE_TOKEN_URI, data=data)
        resp.raise_for_status()
        return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    settings = get_effective_settings()
    data = {
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(GOOGLE_TOKEN_URI, data=data)
        resp.raise_for_status()
        return resp.json()


def revoke_token(token: str) -> None:
    with httpx.Client(timeout=15) as client:
        client.post(GOOGLE_REVOKE_URI, params={"token": token})


def fetch_user_email(access_token: str) -> str:
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
    email = data.get("email")
    if not email:
        raise ValueError("Could not read Google account email")
    return str(email)
