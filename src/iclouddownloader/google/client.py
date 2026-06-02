from __future__ import annotations

from typing import Any

import httpx

from iclouddownloader.db.models import User
from iclouddownloader.google.oauth import refresh_access_token
from iclouddownloader.secrets.token_cipher import decrypt_refresh_token

PHOTOS_API_BASE = "https://photoslibrary.googleapis.com/v1"


class GooglePhotosClient:
    def __init__(self, access_token: str):
        self._access_token = access_token

    @classmethod
    def for_user(cls, user: User) -> GooglePhotosClient:
        if not user.google_refresh_token_encrypted:
            raise ValueError("Google Photos is not connected for this user")
        refresh = decrypt_refresh_token(user.google_refresh_token_encrypted)
        tokens = refresh_access_token(refresh)
        return cls(tokens["access_token"])

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def list_media_items(
        self, *, page_size: int = 100, page_token: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"pageSize": page_size}
        if page_token:
            params["pageToken"] = page_token
        with httpx.Client(timeout=60) as client:
            resp = client.get(
                f"{PHOTOS_API_BASE}/mediaItems",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    def download_bytes(self, base_url: str, variant: str = "d") -> bytes:
        url = f"{base_url}={variant}"
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            resp = client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.content
