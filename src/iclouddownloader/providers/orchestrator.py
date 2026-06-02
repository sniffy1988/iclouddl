from __future__ import annotations

import logging
import threading
from sqlalchemy.orm import Session

from iclouddownloader.db.models import PhotoSource, SyncRun, SyncRunScope, User
from iclouddownloader.db.session import get_session_factory
from iclouddownloader.google.sync import GooglePhotoSyncEngine
from iclouddownloader.icloud.sync import PhotoSyncEngine
from iclouddownloader.providers.base import (
    ProviderSyncResult,
    apply_provider_result_to_run,
    linked_providers,
    max_workers_for_user,
)
from iclouddownloader.providers.cancel import is_sync_cancel_requested
from iclouddownloader.services.auth_service import AuthService
from iclouddownloader.services.google_auth_service import GoogleAuthService

logger = logging.getLogger(__name__)


def _run_icloud(
    user_id: int, max_workers: int, password: str | None, sync_run_id: int | None
) -> ProviderSyncResult:
    db = get_session_factory()()
    try:
        user = db.get(User, user_id)
        if not user:
            return ProviderSyncResult(PhotoSource.icloud, success=False, error="user not found")
        if not user.apple_id or not AuthService.is_authorized(user):
            return ProviderSyncResult(PhotoSource.icloud, success=False, error="not_authorized")
        return PhotoSyncEngine(db, max_workers=max_workers).execute_sync(
            user, password=password, sync_run_id=sync_run_id
        )
    except Exception as e:
        logger.exception("iCloud provider sync failed")
        return ProviderSyncResult(PhotoSource.icloud, success=False, error=str(e))
    finally:
        db.close()


def _run_google(user_id: int, max_workers: int, sync_run_id: int | None) -> ProviderSyncResult:
    db = get_session_factory()()
    try:
        user = db.get(User, user_id)
        if not user:
            return ProviderSyncResult(PhotoSource.google_photos, success=False, error="user not found")
        if not GoogleAuthService.is_authorized(user):
            return ProviderSyncResult(PhotoSource.google_photos, success=False, error="not_authorized")
        return GooglePhotoSyncEngine(db, max_workers=max_workers).execute_sync(
            user, sync_run_id=sync_run_id
        )
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

        run_id = sync_run.id
        if source == PhotoSource.icloud:
            thread = threading.Thread(
                target=lambda uid=user.id, w=workers, pwd=password, rid=run_id: _collect(
                    _run_icloud(uid, w, pwd, rid)
                ),
                daemon=True,
            )
        else:
            thread = threading.Thread(
                target=lambda uid=user.id, w=workers, rid=run_id: _collect(_run_google(uid, w, rid)),
                daemon=True,
            )
        threads.append(thread)
        thread.start()

    while any(t.is_alive() for t in threads):
        if is_sync_cancel_requested(db, sync_run.id):
            break
        for thread in threads:
            thread.join(timeout=0.5)

    for thread in threads:
        thread.join(timeout=0.1)

    merged = ProviderSyncResult(
        source=PhotoSource.icloud,
        photos_discovered=sum(r.photos_discovered for r in results),
        photos_downloaded=sum(r.photos_downloaded for r in results),
        photos_failed=sum(r.photos_failed for r in results),
        photos_skipped=sum(r.photos_skipped for r in results),
        success=any(r.success for r in results),
        cancelled=any(r.cancelled for r in results)
        or is_sync_cancel_requested(db, sync_run.id),
    )
    errors = [f"{r.source.value}: {r.error}" for r in results if r.error and not r.cancelled]
    if merged.cancelled:
        merged.success = False
        merged.error = "cancelled"
    elif not merged.success:
        merged.error = "\n".join(errors) or "All providers failed"

    apply_provider_result_to_run(sync_run, merged)
    user.last_sync_at = sync_run.finished_at
    if merged.cancelled:
        user.last_sync_status = "idle"
    else:
        user.last_sync_status = "completed" if merged.success else "failed"
    db.commit()
    db.refresh(sync_run)

    if notifier:
        try:
            if merged.cancelled:
                pass
            elif merged.success:
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
        if immich_notify and merged.success and not merged.cancelled:
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
