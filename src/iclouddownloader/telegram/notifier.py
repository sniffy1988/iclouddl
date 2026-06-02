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

    def send_sync(self, text: str) -> None:
        if not self.enabled:
            return
        try:
            asyncio.get_event_loop().run_until_complete(self._send(text))
        except RuntimeError:
            asyncio.run(self._send(text))
        except Exception:
            logger.exception("Failed to send Telegram message")

    def sync_started(self, user: User) -> None:
        self.send_sync(f"[{user.apple_id}] Sync started")

    def sync_completed(self, user: User, payload: dict) -> None:
        self.send_sync(
            f"[{user.apple_id}] Sync complete: "
            f"{payload.get('downloaded', 0)} new, "
            f"{payload.get('failed', 0)} failed, "
            f"{payload.get('skipped', 0)} skipped"
        )

    def sync_failed(self, user: User, error: str) -> None:
        self.send_sync(f"[{user.apple_id}] Sync failed: {error}")

    def sync_progress(self, user: User, payload: dict) -> None:
        pass  # avoid spam; only log significant events

    def auth_required(self, user: User, challenge_type: str) -> None:
        self.send_sync(
            f"[{user.apple_id}] Enter Apple verification code (expires in 5 min).\n"
            f"Reply with: /code 123456"
        )

    def admin_message(self, text: str) -> None:
        self.send_sync(text)

    async def test_message(self) -> bool:
        return await self._send("iCloud Photo Downloader: test message OK")
