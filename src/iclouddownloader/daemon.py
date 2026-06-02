from __future__ import annotations

import logging
import signal
import sys
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler

from iclouddownloader.services.runtime_settings_service import get_effective_settings
from iclouddownloader.db.session import get_session_factory
from iclouddownloader.services.auth_service import AuthService
from iclouddownloader.services.sync_service import SyncService
from iclouddownloader.services.user_service import UserService
from iclouddownloader.telegram.bot import run_telegram_bot
from iclouddownloader.notifications import AppNotifier

logger = logging.getLogger(__name__)
_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info("Received signal %s, shutting down...", signum)
    _shutdown = True


def _sync_user(user_id: int, notifier: AppNotifier) -> None:
    db = get_session_factory()()
    try:
        sync_svc = SyncService(db, notifier=notifier)
        sync_svc.trigger_sync(user_id)
    except Exception:
        logger.exception("Scheduled sync failed for user %s", user_id)
    finally:
        db.close()


def _poll_due_users(notifier: AppNotifier) -> None:
    db = get_session_factory()()
    try:
        user_svc = UserService(db)
        auth_svc = AuthService(db)
        auth_svc.expire_stale_challenges()
        due = user_svc.users_due_for_sync()
        if due:
            logger.info("Found %d users due for sync", len(due))
        for user in due:
            if _shutdown:
                break
            threading.Thread(
                target=_sync_user,
                args=(user.id, notifier),
                daemon=True,
            ).start()
    finally:
        db.close()


def run_daemon() -> None:
    from iclouddownloader.logging_setup import configure_logging

    configure_logging(force=True)
    settings = get_effective_settings()
    notifier = AppNotifier()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    if settings.telegram_enabled:
        tg_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        tg_thread.start()
        notifier.daemon_started()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _poll_due_users,
        "interval",
        seconds=settings.scheduler_poll_seconds,
        args=[notifier],
        id="poll_due_users",
    )
    scheduler.start()
    logger.info("Daemon started, polling every %ss", settings.scheduler_poll_seconds)

    try:
        while not _shutdown:
            time.sleep(1)
    finally:
        scheduler.shutdown(wait=False)
        if settings.telegram_enabled:
            notifier.daemon_stopped()
        logger.info("Daemon stopped")


if __name__ == "__main__":
    run_daemon()
