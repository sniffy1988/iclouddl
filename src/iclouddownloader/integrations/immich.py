"""Trigger Immich external library scans after iCloud downloads complete."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import httpx

from iclouddownloader.services.runtime_settings_service import get_effective_settings

if TYPE_CHECKING:
    from iclouddownloader.db.models import User

logger = logging.getLogger(__name__)

_last_scan_at: dict[str, float] = {}
_debounce_lock = threading.Lock()


class ImmichClient:
    """Connection in Settings (DB); each user links an external library ID."""

    def __init__(self) -> None:
        self.settings = get_effective_settings()

    @property
    def configured(self) -> bool:
        return (
            self.settings.immich_enabled
            and bool(self.settings.immich_base_url.strip())
            and bool(self.settings.immich_api_key.strip())
        )

    @staticmethod
    def library_id_for_user(user: User) -> str | None:
        lid = (user.immich_library_id or "").strip()
        return lid or None

    def should_scan_after_sync(self, user: User) -> bool:
        if not self.configured:
            return False
        if not user.immich_scan_after_sync:
            return False
        return self.library_id_for_user(user) is not None

    def list_libraries(self) -> tuple[bool, list[dict] | str]:
        if not self.configured:
            return False, "Configure Immich URL and API key in Settings"
        base = self.settings.immich_base_url.rstrip("/")
        url = f"{base}/api/libraries"
        headers = {"x-api-key": self.settings.immich_api_key, "Accept": "application/json"}
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                return False, f"Immich API {resp.status_code}: {resp.text[:200]}"
            data = resp.json()
            libraries = data if isinstance(data, list) else data.get("libraries", data)
            if not isinstance(libraries, list):
                return False, "Unexpected libraries response"
            external = [
                {
                    "id": lib.get("id"),
                    "name": lib.get("name") or lib.get("id"),
                    "importPaths": lib.get("importPaths") or [],
                }
                for lib in libraries
                if lib.get("id")
            ]
            return True, external
        except Exception as e:
            logger.exception("Immich list libraries failed")
            return False, str(e)

    def trigger_library_scan(
        self,
        library_id: str,
        *,
        refresh_modified: bool = True,
        refresh_all: bool = False,
        force: bool = False,
    ) -> tuple[bool, str]:
        if not self.configured:
            return False, "Immich is not configured in Settings"

        library_id = library_id.strip()
        debounce = max(self.settings.immich_scan_debounce_seconds, 0)
        debounce_key = f"{self.settings.immich_base_url.rstrip('/')}:{library_id}"

        if not force and debounce > 0:
            with _debounce_lock:
                last = _last_scan_at.get(debounce_key, 0.0)
                if time.monotonic() - last < debounce:
                    return True, f"Scan skipped (debounced, wait {debounce}s)"

        base = self.settings.immich_base_url.rstrip("/")
        url = f"{base}/api/libraries/{library_id}/scan"
        headers = {
            "x-api-key": self.settings.immich_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {
            "refreshAllFiles": refresh_all,
            "refreshModifiedFiles": refresh_modified,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, json=body)
            if resp.status_code in (200, 204):
                with _debounce_lock:
                    _last_scan_at[debounce_key] = time.monotonic()
                return True, "Immich library scan queued"
            return False, f"Immich API {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            logger.exception("Immich library scan failed")
            return False, str(e)

    def after_sync_completed(self, user: User, payload: dict) -> tuple[bool, str]:
        if not self.should_scan_after_sync(user):
            return False, "Immich not linked for this user or disabled in Settings"

        library_id = self.library_id_for_user(user)
        if not library_id:
            return False, "No external library ID on user"

        downloaded = int(payload.get("downloaded", 0) or 0)
        refresh_all = downloaded == 0 and int(payload.get("skipped", 0) or 0) == 0
        return self.trigger_library_scan(
            library_id,
            refresh_modified=True,
            refresh_all=refresh_all,
        )

    async def test_connection(self, library_id: str | None = None) -> tuple[bool, str]:
        if not self.configured:
            return False, "Enable Immich and set server URL + API key in Settings"
        ok, result = self.list_libraries()
        if not ok:
            return False, str(result)
        if library_id:
            return self.trigger_library_scan(library_id, force=True)
        libs = result
        if isinstance(libs, list) and libs:
            names = ", ".join(f"{lib.get('name', '?')}" for lib in libs[:5])
            extra = f" (+{len(libs) - 5} more)" if len(libs) > 5 else ""
            return True, f"Connected — {len(libs)} librar{'y' if len(libs) == 1 else 'ies'}: {names}{extra}"
        return True, "Connected — no libraries returned (check API key permissions)"


def immich_fields_for_api(user: User) -> dict:
    return {
        "immich_library_id": user.immich_library_id,
        "immich_scan_after_sync": user.immich_scan_after_sync,
    }
