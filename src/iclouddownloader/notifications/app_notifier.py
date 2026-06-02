"""Telegram alerts + Immich external library scan after sync."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from iclouddownloader.integrations.immich import ImmichClient
from iclouddownloader.telegram.notifier import TelegramNotifier

if TYPE_CHECKING:
    from iclouddownloader.db.models import User

logger = logging.getLogger(__name__)


class AppNotifier:
    def __init__(self) -> None:
        self._telegram = TelegramNotifier()
        self._immich = ImmichClient()

    def sync_started(self, user: User) -> None:
        self._telegram.sync_started(user)

    def sync_completed(self, user: User, payload: dict) -> None:
        self._telegram.sync_completed(user, payload)

    def immich_after_sync(self, user: User, payload: dict) -> None:
        ok, msg = self._immich.after_sync_completed(user, payload)
        if ok:
            logger.info("[%s] %s", user.apple_id, msg)
            if self._telegram.enabled and user.telegram_notify:
                self._telegram.send_sync(f"[{user.apple_id}] Immich: {msg}")
        elif self._immich.should_scan_after_sync(user):
            logger.warning("[%s] Immich scan failed: %s", user.apple_id, msg)
            if self._telegram.enabled and user.telegram_notify:
                self._telegram.send_sync(f"[{user.apple_id}] Immich scan failed: {msg}")

    def sync_failed(self, user: User, error: str) -> None:
        if user.telegram_notify:
            self._telegram.sync_failed(user, error)

    def sync_progress(self, user: User, payload: dict) -> None:
        if user.telegram_notify:
            self._telegram.sync_progress(user, payload)

    def auth_required(self, user: User, challenge_type: str) -> None:
        if user.telegram_notify:
            self._telegram.auth_required(user, challenge_type)

    def admin_message(self, text: str) -> None:
        self._telegram.admin_message(text)

    async def test_telegram(self) -> bool:
        return await self._telegram.test_message()

