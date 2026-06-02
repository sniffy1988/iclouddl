from __future__ import annotations

import hashlib
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.config import get_settings
from iclouddownloader.path_template import apply_path_template
from iclouddownloader.services.runtime_settings_service import get_effective_settings
from iclouddownloader.db.models import Photo, PhotoStatus, SyncCursor, SyncRun, SyncRunStatus, User
from iclouddownloader.events import SyncEvent, get_event_bus
from iclouddownloader.icloud.auth import AuthRequired, get_pyicloud_service
from iclouddownloader.icloud.client import cookie_dir_for_user
from iclouddownloader.icloud.assets import asset_date as _asset_date
from iclouddownloader.icloud.assets import asset_filename as _asset_filename
from iclouddownloader.icloud.assets import asset_id as _asset_id
from iclouddownloader.icloud.library import list_library_photos

logger = logging.getLogger(__name__)


def _local_path(base: Path, photo: Any, filename: str, path_template: str | None = None) -> Path:
    dt = _asset_date(photo) or datetime.now(timezone.utc)
    template = path_template or get_effective_settings().download_path_template
    return base / apply_path_template(template, dt, filename)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_asset(photo: Any, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = photo.download()
    if hasattr(response, "raw"):
        with dest.open("wb") as f:
            shutil.copyfileobj(response.raw, f)
    elif hasattr(response, "read"):
        with dest.open("wb") as f:
            shutil.copyfileobj(response, f)
    else:
        with dest.open("wb") as f:
            f.write(response)


class PhotoSyncEngine:
    def __init__(self, db: Session, notifier: Any | None = None):
        self.db = db
        self.notifier = notifier
        self.settings = get_settings()

    def _get_or_create_cursor(self, user: User) -> SyncCursor:
        cursor = self.db.scalar(
            select(SyncCursor).where(
                SyncCursor.user_id == user.id,
                SyncCursor.library_key == user.library_key,
            )
        )
        if not cursor:
            cursor = SyncCursor(user_id=user.id, library_key=user.library_key)
            self.db.add(cursor)
            self.db.flush()
        return cursor

    def _publish(self, event_type: str, user: User, sync_run: SyncRun | None = None, **payload):
        get_event_bus().publish(
            SyncEvent(
                type=event_type,
                user_id=user.id,
                apple_id=user.apple_id,
                sync_run_id=sync_run.id if sync_run else None,
                payload=payload,
            )
        )
        if self.notifier and user.telegram_notify:
            self._notify_telegram(event_type, user, payload)

    def _notify_telegram(self, event_type: str, user: User, payload: dict):
        if not self.notifier:
            return
        try:
            if event_type == "sync.started":
                self.notifier.sync_started(user)
            elif event_type == "sync.completed":
                self.notifier.sync_completed(user, payload)
            elif event_type == "sync.failed":
                self.notifier.sync_failed(user, payload.get("error", "unknown"))
            elif event_type == "sync.progress":
                self.notifier.sync_progress(user, payload)
        except Exception:
            logger.exception("Telegram notify failed")

    def _photo_exists(self, user_id: int, asset_id: str) -> Photo | None:
        return self.db.scalar(
            select(Photo).where(Photo.user_id == user_id, Photo.icloud_asset_id == asset_id)
        )

    def _process_photo(
        self,
        user: User,
        api_photo: Any,
        base_dir: Path,
        sync_run: SyncRun,
    ) -> str:
        asset_id = _asset_id(api_photo)
        filename = _asset_filename(api_photo)
        existing = self._photo_exists(user.id, asset_id)

        if existing and existing.status == PhotoStatus.downloaded:
            if existing.local_path and Path(existing.local_path).exists():
                sync_run.photos_skipped += 1
                return "skipped"

        dest = _local_path(base_dir, api_photo, filename)
        record = existing or Photo(
            user_id=user.id,
            icloud_asset_id=asset_id,
            filename=filename,
            status=PhotoStatus.pending,
            asset_date=_asset_date(api_photo),
            media_type=getattr(api_photo, "media_type", None),
        )
        if not existing:
            self.db.add(record)

        try:
            _download_asset(api_photo, dest)
            checksum = _sha256(dest)
            record.local_path = str(dest)
            record.file_size = dest.stat().st_size
            record.checksum_sha256 = checksum
            record.status = PhotoStatus.downloaded
            record.downloaded_at = datetime.now(timezone.utc)
            record.error_message = None
            sync_run.photos_downloaded += 1
            return "downloaded"
        except Exception as e:
            record.status = PhotoStatus.failed
            record.error_message = str(e)
            sync_run.photos_failed += 1
            logger.exception("Failed to download %s for user %s", asset_id, user.apple_id)
            return "failed"

    def _iter_photos(self, api) -> list[Any]:
        return list_library_photos(api)

    def run_sync(self, user: User, password: str | None = None) -> SyncRun:
        sync_run = SyncRun(user_id=user.id, status=SyncRunStatus.running)
        self.db.add(sync_run)
        self.db.commit()
        self.db.refresh(sync_run)

        self._publish("sync.started", user, sync_run)
        user.last_sync_status = "syncing"
        self.db.commit()

        try:
            cookie_dir = cookie_dir_for_user(user.id)
            api = get_pyicloud_service(user, password=password, cookie_directory=cookie_dir)
            base_dir = Path(user.download_dir)
            base_dir.mkdir(parents=True, exist_ok=True)

            photos = self._iter_photos(api)
            sync_run.photos_discovered = len(photos)
            self.db.commit()

            max_workers = self.settings.max_concurrent_downloads
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {
                    pool.submit(self._process_photo, user, p, base_dir, sync_run): p
                    for p in photos
                }
                done = 0
                for future in as_completed(futures):
                    future.result()
                    done += 1
                    if done % 10 == 0:
                        self.db.commit()
                        self._publish(
                            "sync.progress",
                            user,
                            sync_run,
                            done=done,
                            total=len(photos),
                        )

            cursor = self._get_or_create_cursor(user)
            cursor.cursor_value = f"synced_{datetime.now(timezone.utc).isoformat()}"
            cursor.updated_at = datetime.now(timezone.utc)

            sync_run.status = SyncRunStatus.completed
            sync_run.finished_at = datetime.now(timezone.utc)
            user.last_sync_at = sync_run.finished_at
            user.last_sync_status = "completed"
            from iclouddownloader.services.auth_service import AuthService

            AuthService(self.db).mark_session_valid(user)
            self.db.commit()

            self._publish(
                "sync.completed",
                user,
                sync_run,
                downloaded=sync_run.photos_downloaded,
                failed=sync_run.photos_failed,
                skipped=sync_run.photos_skipped,
            )
            return sync_run

        except AuthRequired as exc:
            from iclouddownloader.services.auth_service import AuthService

            auth_svc = AuthService(self.db)
            auth_svc.handle_background_auth_required(user)
            sync_run.status = SyncRunStatus.failed
            sync_run.error_summary = "Authentication required"
            sync_run.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            self._publish("sync.failed", user, sync_run, error="auth_required")
            if self.notifier and user.telegram_notify:
                auth_svc.notify_reauth_needed(user, exc.challenge_type.value, self.notifier)
            return sync_run

        except Exception as e:
            sync_run.status = SyncRunStatus.failed
            sync_run.error_summary = str(e)
            sync_run.finished_at = datetime.now(timezone.utc)
            user.last_sync_status = "failed"
            self.db.commit()
            self._publish("sync.failed", user, sync_run, error=str(e))
            logger.exception("Sync failed for user %s", user.apple_id)
            return sync_run
