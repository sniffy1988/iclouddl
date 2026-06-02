"""Daemon status alerts (Telegram) and Immich scans after sync."""

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

    def daemon_started(self) -> None:
        self._telegram.daemon_started()

    def daemon_stopped(self) -> None:
        self._telegram.daemon_stopped()

    def user_added(self, user: User) -> None:
        self._telegram.user_added(user)

    def user_removed(self, user: User) -> None:
        self._telegram.user_removed(user)

    def sync_queued(self, user: User) -> None:
        self._telegram.sync_queued(user)

    def sync_started(self, user: User) -> None:
        self._telegram.sync_started(user)

    def sync_completed(self, user: User, payload: dict) -> None:
        self._telegram.sync_completed(user, payload)

    def sync_failed(self, user: User, error: str) -> None:
        self._telegram.sync_failed(user, error)

    def count_started(self, user: User) -> None:
        self._telegram.count_started(user)

    def count_completed(self, user: User, payload: dict) -> None:
        self._telegram.count_completed(user, payload)

    def count_failed(self, user: User, error: str) -> None:
        self._telegram.count_failed(user, error)

    def immich_after_sync(self, user: User, payload: dict) -> None:
        ok, msg = self._immich.after_sync_completed(user, payload)
        if ok:
            logger.info("[%s] %s", user.apple_id, msg)
        elif self._immich.should_scan_after_sync(user):
            logger.warning("[%s] Immich scan failed: %s", user.apple_id, msg)

    async def test_telegram(self) -> bool:
        return await self._telegram.test_message()
