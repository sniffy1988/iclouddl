from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

from iclouddownloader.services.runtime_settings_service import get_effective_settings

if TYPE_CHECKING:
    from iclouddownloader.db.models import User

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Admin-channel messages for daemon / worker operational status only."""

    def __init__(self):
        self.settings = get_effective_settings()

    @property
    def enabled(self) -> bool:
        return (
            self.settings.telegram_enabled
            and bool(self.settings.telegram_bot_token)
            and bool(self.settings.telegram_admin_chat_id)
        )

    async def _send(self, text: str) -> bool:
        if not self.enabled:
            return False
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"chat_id": self.settings.telegram_admin_chat_id, "text": text},
                timeout=30,
            )
            return resp.is_success

    def send_status(self, text: str) -> None:
        if not self.enabled:
            return
        try:
            asyncio.get_event_loop().run_until_complete(self._send(text))
        except RuntimeError:
            asyncio.run(self._send(text))
        except Exception:
            logger.exception("Failed to send Telegram message")

    def daemon_started(self) -> None:
        self.send_status("Daemon started")

    def daemon_stopped(self) -> None:
        self.send_status("Daemon stopped")

    def user_added(self, user: User) -> None:
        self.send_status(f"User added: {user.apple_id} (id={user.id})")

    def user_removed(self, user: User) -> None:
        self.send_status(f"User removed: {user.apple_id} (id={user.id})")

    def sync_queued(self, user: User) -> None:
        self.send_status(f"[{user.apple_id}] Sync queued")

    def sync_started(self, user: User) -> None:
        self.send_status(f"[{user.apple_id}] Sync started")

    def sync_completed(self, user: User, payload: dict) -> None:
        self.send_status(
            f"[{user.apple_id}] Sync finished: "
            f"{payload.get('downloaded', 0)} new, "
            f"{payload.get('failed', 0)} failed, "
            f"{payload.get('skipped', 0)} skipped"
        )

    def sync_failed(self, user: User, error: str) -> None:
        self.send_status(f"[{user.apple_id}] Sync failed: {error}")

    def count_started(self, user: User) -> None:
        self.send_status(f"[{user.apple_id}] Photo count started")

    def count_completed(self, user: User, payload: dict) -> None:
        total = payload.get("icloud_photos_count")
        self.send_status(
            f"[{user.apple_id}] Photo count finished: {total if total is not None else '?'} photos"
        )

    def count_failed(self, user: User, error: str) -> None:
        self.send_status(f"[{user.apple_id}] Photo count failed: {error}")

    async def test_message(self) -> bool:
        return await self._send("iCloud Photo Downloader: daemon status test OK")
