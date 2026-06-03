from __future__ import annotations

import logging

from iclouddownloader.db.models import PhotoSource
from iclouddownloader.db.session import get_session_factory
from iclouddownloader.icloud.auth import AuthRequired
from iclouddownloader.services.sync_service import SyncService
from iclouddownloader.services.user_service import UserService

logger = logging.getLogger(__name__)

JOB_TIMEOUT = 60 * 60 * 24  # 24h for full-library sync/count


def task_fetch_photo_count(user_id: int, source: str) -> None:
    from iclouddownloader.logging_setup import configure_rq_job_logging

    configure_rq_job_logging(force=True)
    photo_source = PhotoSource(source)
    db = get_session_factory()()
    try:
        logger.info("RQ count job started for user %s source %s", user_id, source)
        logger.info("RQ count job opening SyncService for user %s", user_id)
        sync_svc = SyncService(db, notifier=None)
        logger.info("RQ count job loading user %s from database", user_id)
        user = sync_svc.user_service.get_user(user_id)
        logger.info("RQ count job user %s found=%s", user_id, user is not None)
        if user:
            sync_svc._event(
                user,
                "count.progress",
                photo_source,
                indexed=0,
                created=0,
                updated=0,
            )
            logger.info("RQ count job published progress(0) for user %s", user_id)
        logger.info("RQ count job calling iCloud/Google index for user %s", user_id)
        sync_svc.fetch_photo_count(user_id, photo_source)
        logger.info("RQ count job finished for user %s source %s", user_id, source)
    except AuthRequired:
        logger.warning("Count job needs iCloud auth for user %s", user_id)
    except Exception as exc:
        logger.exception("Count job failed for user %s source %s", user_id, source)
        sync_svc = SyncService(db, notifier=None)
        user = sync_svc.user_service.get_user(user_id)
        if user:
            sync_svc._event(user, "count.failed", photo_source, error=str(exc))
            if user.last_sync_status in (
                "counting",
                "counting_icloud",
                "counting_google",
            ):
                user.last_sync_status = "idle"
                db.commit()
    finally:
        db.close()


def task_trigger_sync(user_id: int, source: str | None = None) -> None:
    from iclouddownloader.logging_setup import configure_rq_job_logging

    configure_rq_job_logging(force=True)
    db = get_session_factory()()
    try:
        photo_source = PhotoSource(source) if source else None
        SyncService(db, notifier=None).trigger_sync(user_id, source=photo_source)
    except Exception:
        logger.exception("Sync job failed for user %s", user_id)
    finally:
        db.close()
