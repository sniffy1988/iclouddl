from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import Photo, PhotoStatus, SyncRun, SyncRunStatus, User
from iclouddownloader.events import SyncEvent, get_event_bus
from iclouddownloader.icloud.auth import AuthRequired, get_pyicloud_service
from iclouddownloader.icloud.client import cookie_dir_for_user
from iclouddownloader.icloud.assets import index_library_to_db
from iclouddownloader.icloud.sync import PhotoSyncEngine
from iclouddownloader.integrations.immich import immich_fields_for_api
from iclouddownloader.services.auth_service import AuthService
from iclouddownloader.services.user_service import UserService


class SyncInProgressError(Exception):
    def __init__(self, user_id: int, sync_run_id: int):
        self.user_id = user_id
        self.sync_run_id = sync_run_id
        super().__init__(f"Sync already running for user {user_id}")


class SyncService:
    def __init__(self, db: Session, notifier=None):
        self.db = db
        self.notifier = notifier
        self.user_service = UserService(db)

    def get_active_sync_run(self, user_id: int) -> SyncRun | None:
        return self.db.scalar(
            select(SyncRun)
            .where(
                SyncRun.user_id == user_id,
                SyncRun.status == SyncRunStatus.running,
            )
            .order_by(SyncRun.started_at.desc())
        )

    def ensure_can_start_sync(self, user_id: int) -> None:
        active = self.get_active_sync_run(user_id)
        if active:
            raise SyncInProgressError(user_id, active.id)

    def mark_sync_queued(self, user_id: int) -> User:
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        user.last_sync_status = "queued"
        self.db.commit()
        self.db.refresh(user)
        return user

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

    def get_pending_download_count(self, user_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count(Photo.id)).where(
                    Photo.user_id == user_id,
                    Photo.status == PhotoStatus.pending,
                )
            )
            or 0
        )

    def build_photo_count_result(self, user: User) -> dict:
        local = self.get_local_photo_stats(user.id)
        icloud_total = user.icloud_photos_count
        remaining = None
        if user.last_sync_status != "counting" and icloud_total is not None:
            pending = self.get_pending_download_count(user.id)
            remaining = max(pending, icloud_total - local["downloaded_count"])
        return {
            "user_id": user.id,
            "icloud_photos_count": icloud_total,
            "icloud_photos_count_at": user.icloud_photos_count_at,
            "downloaded_count": local["downloaded_count"],
            "tracked_count": local["tracked_count"],
            "remaining_to_download": remaining,
        }

    def user_to_response(self, user: User) -> dict:
        """User fields plus local download stats for API/UI."""
        stats = self.build_photo_count_result(user)
        return {
            "id": user.id,
            "apple_id": user.apple_id,
            "display_name": user.display_name,
            "download_dir": user.download_dir,
            "sync_interval_seconds": user.sync_interval_seconds,
            "enabled": user.enabled,
            "library_key": user.library_key,
            "telegram_notify": user.telegram_notify,
            "next_sync_at": user.next_sync_at,
            "last_sync_at": user.last_sync_at,
            "last_sync_status": user.last_sync_status,
            "auth_status": AuthService.auth_status_for_user(user),
            "activity_status": AuthService.activity_status_for_user(user),
            "icloud_photos_count": user.icloud_photos_count,
            "icloud_photos_count_at": user.icloud_photos_count_at,
            "downloaded_count": stats["downloaded_count"],
            "remaining_to_download": stats["remaining_to_download"],
            "icloud_authenticated_at": user.icloud_authenticated_at,
            "icloud_2fa_at": user.icloud_2fa_at,
            "icloud_session_ok_at": user.icloud_session_ok_at,
            "icloud_needs_auth": user.icloud_needs_auth,
            "icloud_authorized": AuthService.is_authorized(user),
            "icloud_2fa_expires_at": AuthService.icloud_2fa_expires_at(user),
            "days_until_2fa_expires": AuthService.days_until_2fa_expires(user),
            **immich_fields_for_api(user),
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    def _publish_count_progress(self, user: User, stats: dict[str, int]) -> None:
        user.icloud_photos_count = stats["indexed"]
        self.db.commit()
        get_event_bus().publish(
            SyncEvent(
                type="count.progress",
                user_id=user.id,
                apple_id=user.apple_id,
                payload=stats,
            )
        )

    def fetch_icloud_photo_count(self, user_id: int, password: str | None = None) -> dict:
        """Scan iCloud library: index metadata into ``photos`` table (no download)."""
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if self.get_active_sync_run(user_id):
            raise SyncInProgressError(user_id, self.get_active_sync_run(user_id).id)  # type: ignore[union-attr]

        get_event_bus().publish(
            SyncEvent(type="count.started", user_id=user.id, apple_id=user.apple_id)
        )
        user.last_sync_status = "counting"
        user.icloud_photos_count = 0
        self.db.commit()

        try:
            cookie_dir = cookie_dir_for_user(user.id)
            api = get_pyicloud_service(user, password=password, cookie_directory=cookie_dir)

            def on_progress(stats: dict[str, int]) -> None:
                self._publish_count_progress(user, stats)

            index_stats = index_library_to_db(
                self.db,
                user,
                api,
                commit_every=200,
                on_progress=on_progress,
            )
            user.icloud_photos_count = index_stats["indexed"]
            user.icloud_photos_count_at = datetime.now(timezone.utc)
            user.last_sync_status = "count_ready"
            from iclouddownloader.services.auth_service import AuthService

            AuthService(self.db).mark_session_valid(user)
            self.db.commit()
            self.db.refresh(user)

            result = self.build_photo_count_result(user)
            result["index_created"] = index_stats["created"]
            result["index_updated"] = index_stats["updated"]
            get_event_bus().publish(
                SyncEvent(
                    type="count.completed",
                    user_id=user.id,
                    apple_id=user.apple_id,
                    payload=result,
                )
            )
            return result

        except AuthRequired:
            from iclouddownloader.services.auth_service import AuthService

            AuthService(self.db).handle_background_auth_required(user)
            get_event_bus().publish(
                SyncEvent(
                    type="count.failed",
                    user_id=user.id,
                    apple_id=user.apple_id,
                    payload={"error": "auth_required"},
                )
            )
            raise

        except Exception as e:
            user.last_sync_status = "count_failed"
            self.db.commit()
            get_event_bus().publish(
                SyncEvent(
                    type="count.failed",
                    user_id=user.id,
                    apple_id=user.apple_id,
                    payload={"error": str(e)},
                )
            )
            raise

    def trigger_sync(self, user_id: int, password: str | None = None) -> SyncRun:
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        engine = PhotoSyncEngine(self.db, notifier=self.notifier)
        sync_run = engine.run_sync(user, password=password)
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
        """Queue manual sync for each enabled user that is due. Returns (user_id, status) pairs."""
        results: list[tuple[int, str]] = []
        for user in self.user_service.users_due_for_sync():
            try:
                self.ensure_can_start_sync(user.id)
                self.mark_sync_queued(user.id)
                results.append((user.id, "queued"))
            except SyncInProgressError:
                results.append((user.id, "already_running"))
        return results
