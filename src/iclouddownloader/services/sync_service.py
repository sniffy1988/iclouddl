from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import Photo, PhotoSource, PhotoStatus, SyncRun, SyncRunScope, SyncRunStatus, User
from iclouddownloader.events import SyncEvent, get_event_bus
from iclouddownloader.google.assets import index_google_library_to_db
from iclouddownloader.google.sync import GooglePhotoSyncEngine
from iclouddownloader.icloud.auth import AuthRequired, get_pyicloud_service
from iclouddownloader.icloud.client import cookie_dir_for_user
from iclouddownloader.icloud.assets import index_library_to_db
from iclouddownloader.icloud.sync import PhotoSyncEngine
from iclouddownloader.integrations.immich import immich_fields_for_api
from iclouddownloader.providers.base import (
    account_label,
    active_sync_runs,
    linked_providers,
    max_workers_for_user,
    scope_for_source,
    sync_scope_conflicts,
)
from iclouddownloader.providers.orchestrator import run_all_providers_parallel
from iclouddownloader.services.auth_service import AuthService
from iclouddownloader.services.google_auth_service import GoogleAuthService
from iclouddownloader.services.user_service import UserService


class SyncInProgressError(Exception):
    def __init__(self, user_id: int, sync_run_id: int, scope: str | None = None):
        self.user_id = user_id
        self.sync_run_id = sync_run_id
        self.scope = scope
        super().__init__(f"Sync already running for user {user_id}")


class SyncService:
    def __init__(self, db: Session, notifier=None):
        self.db = db
        self.notifier = notifier
        self.user_service = UserService(db)

    def get_active_sync_runs(self, user_id: int) -> list[SyncRun]:
        return active_sync_runs(self.db, user_id)

    def get_active_sync_run(self, user_id: int) -> SyncRun | None:
        runs = self.get_active_sync_runs(user_id)
        return runs[0] if runs else None

    def ensure_can_start_sync(
        self,
        user_id: int,
        requested: PhotoSource | None = None,
    ) -> None:
        requested_scope = scope_for_source(requested)
        for run in self.get_active_sync_runs(user_id):
            if sync_scope_conflicts(run.scope, requested_scope):
                raise SyncInProgressError(user_id, run.id, scope=run.scope.value)

    def active_syncs_by_scope(self, user_id: int) -> dict[str, bool]:
        running = self.get_active_sync_runs(user_id)
        scopes = {r.scope.value for r in running}
        return {
            "icloud": SyncRunScope.all.value in scopes or SyncRunScope.icloud.value in scopes,
            "google_photos": SyncRunScope.all.value in scopes
            or SyncRunScope.google_photos.value in scopes,
            "all": SyncRunScope.all.value in scopes,
        }

    def mark_sync_queued(self, user_id: int) -> User:
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        user.last_sync_status = "queued"
        self.db.commit()
        self.db.refresh(user)
        if self.notifier:
            self.notifier.sync_queued(user)
        return user

    def _stats_for_source(self, user_id: int, source: PhotoSource) -> dict[str, int]:
        downloaded = (
            self.db.scalar(
                select(func.count(Photo.id)).where(
                    Photo.user_id == user_id,
                    Photo.source == source,
                    Photo.status == PhotoStatus.downloaded,
                )
            )
            or 0
        )
        pending = (
            self.db.scalar(
                select(func.count(Photo.id)).where(
                    Photo.user_id == user_id,
                    Photo.source == source,
                    Photo.status == PhotoStatus.pending,
                )
            )
            or 0
        )
        return {"downloaded": downloaded, "pending": pending}

    def get_local_photo_stats(self, user_id: int) -> dict[str, int]:
        downloaded = (
            self.db.scalar(
                select(func.count(Photo.id)).where(
                    Photo.user_id == user_id,
                    Photo.status == PhotoStatus.downloaded,
                )
            )
            or 0
        )
        tracked = (
            self.db.scalar(select(func.count(Photo.id)).where(Photo.user_id == user_id)) or 0
        )
        return {"downloaded_count": downloaded, "tracked_count": tracked}

    def build_photo_count_result(self, user: User, source: PhotoSource | None = None) -> dict:
        local = self.get_local_photo_stats(user.id)
        icloud_stats = self._stats_for_source(user.id, PhotoSource.icloud)
        google_stats = self._stats_for_source(user.id, PhotoSource.google_photos)

        def _remaining(total: int | None, downloaded: int, pending: int) -> int | None:
            if total is None:
                return None
            return max(pending, total - downloaded)

        icloud_remaining = _remaining(
            user.icloud_photos_count, icloud_stats["downloaded"], icloud_stats["pending"]
        )
        google_remaining = _remaining(
            user.google_photos_count, google_stats["downloaded"], google_stats["pending"]
        )

        result = {
            "user_id": user.id,
            "source": source.value if source else None,
            "icloud_photos_count": user.icloud_photos_count,
            "icloud_photos_count_at": user.icloud_photos_count_at,
            "google_photos_count": user.google_photos_count,
            "google_photos_count_at": user.google_photos_count_at,
            "downloaded_count": local["downloaded_count"],
            "tracked_count": local["tracked_count"],
            "icloud_downloaded_count": icloud_stats["downloaded"],
            "google_downloaded_count": google_stats["downloaded"],
            "icloud_remaining": icloud_remaining,
            "google_remaining": google_remaining,
            "remaining_to_download": None,
        }
        if icloud_remaining is not None and google_remaining is not None:
            result["remaining_to_download"] = icloud_remaining + google_remaining
        elif source == PhotoSource.icloud:
            result["remaining_to_download"] = icloud_remaining
        elif source == PhotoSource.google_photos:
            result["remaining_to_download"] = google_remaining
        else:
            parts = [x for x in (icloud_remaining, google_remaining) if x is not None]
            result["remaining_to_download"] = sum(parts) if parts else None
        return result

    def user_to_response(self, user: User) -> dict:
        stats = self.build_photo_count_result(user)
        label = account_label(user)
        pending_icloud = AuthService(self.db).get_pending_challenge(user.id) is not None
        icloud_status = AuthService.icloud_auth_status(user, pending_challenge=pending_icloud)
        return {
            "id": user.id,
            "apple_id": user.apple_id,
            "display_name": user.display_name,
            "account_label": label,
            "download_dir": user.download_dir,
            "sync_interval_seconds": user.sync_interval_seconds,
            "enabled": user.enabled,
            "library_key": user.library_key,
            "next_sync_at": user.next_sync_at,
            "last_sync_at": user.last_sync_at,
            "last_sync_status": user.last_sync_status,
            "auth_status": icloud_status,
            "icloud_auth_status": icloud_status,
            "icloud_pending_challenge": pending_icloud,
            "google_auth_status": GoogleAuthService.google_auth_status(user),
            "activity_status": AuthService.activity_status_for_user(user),
            "icloud_photos_count": user.icloud_photos_count,
            "icloud_photos_count_at": user.icloud_photos_count_at,
            "google_photos_count": user.google_photos_count,
            "google_photos_count_at": user.google_photos_count_at,
            "google_account_email": user.google_account_email,
            "downloaded_count": stats["downloaded_count"],
            "icloud_downloaded_count": stats["icloud_downloaded_count"],
            "google_downloaded_count": stats["google_downloaded_count"],
            "icloud_remaining": stats["icloud_remaining"],
            "google_remaining": stats["google_remaining"],
            "remaining_to_download": stats["remaining_to_download"],
            "icloud_authenticated_at": user.icloud_authenticated_at,
            "icloud_2fa_at": user.icloud_2fa_at,
            "icloud_session_ok_at": user.icloud_session_ok_at,
            "icloud_needs_auth": user.icloud_needs_auth,
            "icloud_authorized": AuthService.is_authorized(user) if user.apple_id else False,
            "google_authorized": GoogleAuthService.is_authorized(user),
            "google_needs_auth": user.google_needs_auth,
            "google_authenticated_at": user.google_authenticated_at,
            "linked_providers": [p.value for p in linked_providers(user)],
            "active_syncs_by_scope": self.active_syncs_by_scope(user.id),
            "icloud_2fa_expires_at": AuthService.icloud_2fa_expires_at(user),
            "days_until_2fa_expires": AuthService.days_until_2fa_expires(user),
            **immich_fields_for_api(user),
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    def _event(self, user: User, event_type: str, source: PhotoSource | None = None, **payload):
        get_event_bus().publish(
            SyncEvent(
                type=event_type,
                user_id=user.id,
                apple_id=user.apple_id,
                account_label=account_label(user),
                source=source.value if source else None,
                payload=payload,
            )
        )

    def fetch_photo_count(
        self,
        user_id: int,
        source: PhotoSource,
        password: str | None = None,
    ) -> dict:
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if source == PhotoSource.icloud:
            if not user.apple_id:
                raise ValueError("iCloud is not linked for this user")
            return self._fetch_icloud_photo_count(user, password)
        if not user.google_refresh_token_encrypted and not user.google_account_email:
            raise ValueError("Google Photos is not linked for this user")
        return self._fetch_google_photo_count(user)

    def _fetch_icloud_photo_count(self, user: User, password: str | None) -> dict:
        self._event(user, "count.started", PhotoSource.icloud)
        if self.notifier:
            self.notifier.count_started(user)
        user.last_sync_status = "counting_icloud"
        user.icloud_photos_count = 0
        self.db.commit()

        try:
            cookie_dir = cookie_dir_for_user(user.id)
            api = get_pyicloud_service(user, password=password, cookie_directory=cookie_dir)

            def on_progress(stats: dict[str, int]) -> None:
                user.icloud_photos_count = stats["indexed"]
                self.db.commit()
                self._event(user, "count.progress", PhotoSource.icloud, **stats)

            index_stats = index_library_to_db(
                self.db, user, api, commit_every=200, on_progress=on_progress
            )
            user.icloud_photos_count = index_stats["indexed"]
            user.icloud_photos_count_at = datetime.now(timezone.utc)
            user.last_sync_status = "count_ready"
            AuthService(self.db).mark_session_valid(user)
            self.db.commit()
            self.db.refresh(user)

            result = self.build_photo_count_result(user, PhotoSource.icloud)
            result["index_created"] = index_stats["created"]
            result["index_updated"] = index_stats["updated"]
            self._event(user, "count.completed", PhotoSource.icloud, **result)
            if self.notifier:
                self.notifier.count_completed(user, result)
            return result

        except AuthRequired:
            AuthService(self.db).handle_background_auth_required(user)
            self._event(user, "count.failed", PhotoSource.icloud, error="auth_required")
            if self.notifier:
                self.notifier.count_failed(user, "auth_required")
            raise

        except Exception as e:
            user.last_sync_status = "count_failed"
            self.db.commit()
            self._event(user, "count.failed", PhotoSource.icloud, error=str(e))
            if self.notifier:
                self.notifier.count_failed(user, str(e))
            raise

    def _fetch_google_photo_count(self, user: User) -> dict:
        self._event(user, "count.started", PhotoSource.google_photos)
        if self.notifier:
            self.notifier.count_started(user)
        user.last_sync_status = "counting_google"
        user.google_photos_count = 0
        self.db.commit()

        try:

            def on_progress(stats: dict[str, int]) -> None:
                user.google_photos_count = stats["indexed"]
                self.db.commit()
                self._event(user, "count.progress", PhotoSource.google_photos, **stats)

            index_stats = index_google_library_to_db(
                self.db, user, commit_every=200, on_progress=on_progress
            )
            user.google_photos_count = index_stats["indexed"]
            user.google_photos_count_at = datetime.now(timezone.utc)
            user.last_sync_status = "count_ready"
            user.google_needs_auth = False
            self.db.commit()
            self.db.refresh(user)

            result = self.build_photo_count_result(user, PhotoSource.google_photos)
            result["index_created"] = index_stats["created"]
            result["index_updated"] = index_stats["updated"]
            self._event(user, "count.completed", PhotoSource.google_photos, **result)
            if self.notifier:
                self.notifier.count_completed(user, result)
            return result

        except Exception as e:
            err = str(e)
            if "401" in err or "invalid_grant" in err.lower():
                user.google_needs_auth = True
            user.last_sync_status = "count_failed"
            self.db.commit()
            self._event(user, "count.failed", PhotoSource.google_photos, error=err)
            if self.notifier:
                self.notifier.count_failed(user, err)
            raise

    def fetch_icloud_photo_count(self, user_id: int, password: str | None = None) -> dict:
        return self.fetch_photo_count(user_id, PhotoSource.icloud, password=password)

    def trigger_sync(
        self,
        user_id: int,
        source: PhotoSource | None = None,
        password: str | None = None,
    ) -> SyncRun:
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        scope = scope_for_source(source)
        sync_run = SyncRun(user_id=user.id, status=SyncRunStatus.running, scope=scope)
        self.db.add(sync_run)
        self.db.commit()
        self.db.refresh(sync_run)

        user.last_sync_status = "syncing"
        self.db.commit()

        if scope == SyncRunScope.all:
            run_all_providers_parallel(
                self.db, user, sync_run, password=password, notifier=self.notifier
            )
        elif scope == SyncRunScope.icloud:
            workers = max_workers_for_user(self.db, user.id, SyncRunScope.icloud)
            PhotoSyncEngine(self.db, notifier=self.notifier, max_workers=workers).run_sync(
                user, password=password, sync_run=sync_run
            )
        else:
            workers = max_workers_for_user(self.db, user.id, SyncRunScope.google_photos)
            GooglePhotoSyncEngine(self.db, notifier=self.notifier, max_workers=workers).run_sync(
                user, sync_run=sync_run
            )

        self.user_service.schedule_next_sync(user)
        return sync_run

    def list_sync_runs(
        self,
        user_id: int | None = None,
        status: SyncRunStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SyncRun]:
        stmt = select(SyncRun).order_by(SyncRun.started_at.desc())
        if user_id:
            stmt = stmt.where(SyncRun.user_id == user_id)
        if status:
            stmt = stmt.where(SyncRun.status == status)
        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def list_photos(
        self,
        user_id: int,
        status: PhotoStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Photo]:
        stmt = select(Photo).where(Photo.user_id == user_id).order_by(Photo.created_at.desc())
        if status:
            stmt = stmt.where(Photo.status == status)
        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def dashboard_stats(self) -> dict:
        total_users = self.db.scalar(select(func.count(User.id))) or 0
        enabled_users = self.db.scalar(select(func.count(User.id)).where(User.enabled.is_(True))) or 0
        total_photos = self.db.scalar(select(func.count(Photo.id))) or 0
        downloaded_today = self.db.scalar(
            select(func.count(Photo.id)).where(
                Photo.status == PhotoStatus.downloaded,
                Photo.downloaded_at >= datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
            )
        ) or 0
        active_syncs = self.db.scalar(
            select(func.count(SyncRun.id)).where(SyncRun.status == SyncRunStatus.running)
        ) or 0
        failed_recent = self.db.scalar(
            select(func.count(SyncRun.id)).where(SyncRun.status == SyncRunStatus.failed)
        ) or 0
        due_users = len(self.user_service.users_due_for_sync())
        return {
            "total_users": total_users,
            "enabled_users": enabled_users,
            "total_photos": total_photos,
            "downloaded_today": downloaded_today,
            "active_syncs": active_syncs,
            "failed_syncs": failed_recent,
            "users_due_for_sync": due_users,
        }

    def trigger_sync_for_due_users(self) -> list[tuple[int, str]]:
        results: list[tuple[int, str]] = []
        for user in self.user_service.users_due_for_sync():
            try:
                self.ensure_can_start_sync(user.id, requested=None)
                self.mark_sync_queued(user.id)
                results.append((user.id, "queued"))
            except SyncInProgressError:
                results.append((user.id, "already_running"))
        return results
