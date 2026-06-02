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
    """Optional daemon status hooks (no outbound channel configured). Token test via getMe."""

    def __init__(self):
        self.settings = get_effective_settings()

    @property
    def enabled(self) -> bool:
        return False

    def send_status(self, text: str) -> None:
        return

    def daemon_started(self) -> None:
        pass

    def daemon_stopped(self) -> None:
        pass

    def user_added(self, user: User) -> None:
        pass

    def user_removed(self, user: User) -> None:
        pass

    def sync_queued(self, user: User) -> None:
        pass

    def sync_started(self, user: User) -> None:
        pass

    def sync_completed(self, user: User, payload: dict) -> None:
        pass

    def sync_failed(self, user: User, error: str) -> None:
        pass

    def count_started(self, user: User) -> None:
        pass

    def count_completed(self, user: User, payload: dict) -> None:
        pass

    def count_failed(self, user: User, error: str) -> None:
        pass

    async def test_bot_token(self) -> bool:
        token = (self.settings.telegram_bot_token or "").strip()
        if not token:
            return False
        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30)
                return resp.is_success
        except Exception:
            logger.exception("Telegram getMe failed")
            return False

    async def test_message(self) -> bool:
        return await self.test_bot_token()
