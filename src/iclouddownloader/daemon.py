from __future__ import annotations

import logging
import os
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from iclouddownloader.jobs.queue import count_queue, enqueue_sync, sync_queue
from iclouddownloader.jobs.worker import create_rq_worker
from iclouddownloader.services.runtime_settings_service import get_effective_settings
from iclouddownloader.db.session import get_session_factory
from iclouddownloader.services.auth_service import AuthService
from iclouddownloader.services.sync_service import SyncInProgressError, SyncService
from iclouddownloader.services.user_service import UserService
from iclouddownloader.telegram.bot import run_telegram_bot
from iclouddownloader.notifications import AppNotifier

logger = logging.getLogger(__name__)


def _poll_due_users(notifier: AppNotifier) -> None:
    db = get_session_factory()()
    try:
        user_svc = UserService(db)
        sync_svc = SyncService(db, notifier=notifier)
        auth_svc = AuthService(db)
        auth_svc.expire_stale_challenges()
        due = user_svc.users_due_for_sync()
        if due:
            logger.info("Found %d users due for sync", len(due))
        for user in due:
            try:
                sync_svc.ensure_can_start_sync(user.id)
                sync_svc.mark_sync_queued(user.id)
                enqueue_sync(user.id)
            except SyncInProgressError:
                logger.debug("Skip due sync for user %s — already running", user.id)
    finally:
        db.close()


def run_daemon() -> None:
    from iclouddownloader.logging_setup import configure_logging

    configure_logging(force=True)
    settings = get_effective_settings()
    notifier = AppNotifier()

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
    logger.info(
        "Worker started (RQ on main thread + scheduler every %ss)",
        settings.scheduler_poll_seconds,
    )

    if hasattr(os, "register_at_fork"):
        from iclouddownloader.jobs.fork_safety import reset_fork_unsafe_globals

        os.register_at_fork(after_in_child=reset_fork_unsafe_globals)

    conn = sync_queue().connection
    worker = create_rq_worker([sync_queue(), count_queue()], connection=conn)
    logger.info(
        "RQ worker listening on queues: %s, %s",
        sync_queue().name,
        count_queue().name,
    )

    try:
        # Must run in main thread (RQ installs SIGINT/SIGTERM handlers).
        worker.work()
    finally:
        scheduler.shutdown(wait=False)
        if settings.telegram_enabled:
            notifier.daemon_stopped()
        logger.info("Worker stopped")


if __name__ == "__main__":
    run_daemon()
