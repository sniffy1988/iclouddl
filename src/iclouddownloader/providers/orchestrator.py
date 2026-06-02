from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from iclouddownloader.db.models import PhotoSource, SyncRun, SyncRunScope, SyncRunStatus, User
from iclouddownloader.db.session import get_session_factory
from iclouddownloader.google.sync import GooglePhotoSyncEngine
from iclouddownloader.icloud.sync import PhotoSyncEngine
from iclouddownloader.providers.base import ProviderSyncResult, linked_providers, max_workers_for_user
from iclouddownloader.services.auth_service import AuthService
from iclouddownloader.services.google_auth_service import GoogleAuthService

logger = logging.getLogger(__name__)


def _run_icloud(user_id: int, max_workers: int, password: str | None) -> ProviderSyncResult:
    db = get_session_factory()()
    try:
        user = db.get(User, user_id)
        if not user:
            return ProviderSyncResult(PhotoSource.icloud, success=False, error="user not found")
        if not user.apple_id or not AuthService.is_authorized(user):
            return ProviderSyncResult(PhotoSource.icloud, success=False, error="not_authorized")
        return PhotoSyncEngine(db, max_workers=max_workers).execute_sync(user, password=password)
    except Exception as e:
        logger.exception("iCloud provider sync failed")
        return ProviderSyncResult(PhotoSource.icloud, success=False, error=str(e))
    finally:
        db.close()


def _run_google(user_id: int, max_workers: int) -> ProviderSyncResult:
    db = get_session_factory()()
    try:
        user = db.get(User, user_id)
        if not user:
            return ProviderSyncResult(PhotoSource.google_photos, success=False, error="user not found")
        if not GoogleAuthService.is_authorized(user):
            return ProviderSyncResult(PhotoSource.google_photos, success=False, error="not_authorized")
        return GooglePhotoSyncEngine(db, max_workers=max_workers).execute_sync(user)
    except Exception as e:
        logger.exception("Google provider sync failed")
        return ProviderSyncResult(PhotoSource.google_photos, success=False, error=str(e))
    finally:
        db.close()


def run_all_providers_parallel(
    db: Session,
    user: User,
    sync_run: SyncRun,
    *,
    password: str | None = None,
    notifier=None,
) -> SyncRun:
    """Run each linked+authorized provider in parallel; merge stats into sync_run (scope=all)."""
    providers = linked_providers(user)
    results: list[ProviderSyncResult] = []
    result_lock = threading.Lock()
    threads: list[threading.Thread] = []

    def _collect(res: ProviderSyncResult):
        with result_lock:
            results.append(res)

    for source in providers:
        if source == PhotoSource.icloud and not AuthService.is_authorized(user):
            results.append(ProviderSyncResult(PhotoSource.icloud, success=False, error="not_authorized"))
            continue
        if source == PhotoSource.google_photos and not GoogleAuthService.is_authorized(user):
            results.append(
                ProviderSyncResult(PhotoSource.google_photos, success=False, error="not_authorized")
            )
            continue

        workers = max_workers_for_user(db, user.id, SyncRunScope.all)

        if source == PhotoSource.icloud:
            thread = threading.Thread(
                target=lambda uid=user.id, w=workers, pwd=password: _collect(_run_icloud(uid, w, pwd)),
                daemon=True,
            )
        else:
            thread = threading.Thread(
                target=lambda uid=user.id, w=workers: _collect(_run_google(uid, w)),
                daemon=True,
            )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    sync_run.photos_discovered = sum(r.photos_discovered for r in results)
    sync_run.photos_downloaded = sum(r.photos_downloaded for r in results)
    sync_run.photos_failed = sum(r.photos_failed for r in results)
    sync_run.photos_skipped = sum(r.photos_skipped for r in results)

    errors = [f"{r.source.value}: {r.error}" for r in results if r.error]
    successes = [r for r in results if r.success]

    if successes:
        sync_run.status = SyncRunStatus.completed
        sync_run.error_summary = "\n".join(errors) if errors else None
    else:
        sync_run.status = SyncRunStatus.failed
        sync_run.error_summary = "\n".join(errors) or "All providers failed"

    sync_run.finished_at = datetime.now(timezone.utc)
    user.last_sync_at = sync_run.finished_at
    user.last_sync_status = "completed" if successes else "failed"
    db.commit()
    db.refresh(sync_run)

    if notifier:
        try:
            if successes:
                notifier.sync_completed(
                    user,
                    {
                        "downloaded": sync_run.photos_downloaded,
                        "failed": sync_run.photos_failed,
                        "skipped": sync_run.photos_skipped,
                    },
                )
            else:
                notifier.sync_failed(user, sync_run.error_summary or "failed")
        except Exception:
            logger.exception("Notifier failed after orchestrated sync")

        immich_notify = getattr(notifier, "immich_after_sync", None)
        if immich_notify and successes:
            try:
                immich_notify(
                    user,
                    {
                        "downloaded": sync_run.photos_downloaded,
                        "failed": sync_run.photos_failed,
                        "skipped": sync_run.photos_skipped,
                    },
                )
            except Exception:
                logger.exception("Immich notify failed")

    return sync_run
