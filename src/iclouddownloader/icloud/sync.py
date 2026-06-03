from __future__ import annotations

import hashlib
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.config import get_settings
from iclouddownloader.path_template import apply_path_template
from iclouddownloader.services.runtime_settings_service import get_effective_settings
from iclouddownloader.db.models import Photo, PhotoSource, PhotoStatus, SyncCursor, SyncRun, SyncRunStatus, User
from iclouddownloader.events import SyncEvent, get_event_bus
from iclouddownloader.icloud.auth import AuthRequired, get_pyicloud_service
from iclouddownloader.icloud.client import cookie_dir_for_user
from iclouddownloader.icloud.assets import asset_date as _asset_date
from iclouddownloader.icloud.assets import asset_filename as _asset_filename
from iclouddownloader.icloud.assets import asset_id as _asset_id
from iclouddownloader.icloud.assets import asset_media_type
from iclouddownloader.icloud.library import list_library_photos
from iclouddownloader.icloud.media import (
    LIVE_VIDEO_PREFIX,
    classify_media_type,
    download_by_prefix,
    download_version,
    has_live_video_component,
    live_video_filename,
    master_fields,
)
from iclouddownloader.paths import provider_download_dir
from iclouddownloader.providers.base import ProviderSyncResult, account_label, apply_provider_result_to_run
from iclouddownloader.providers.cancel import drain_futures_with_cancel, is_sync_cancel_requested

logger = logging.getLogger(__name__)


def _local_path(base: Path, photo: Any, filename: str, path_template: str | None = None) -> Path:
    dt = _asset_date(photo) or datetime.now(timezone.utc)
    template = path_template or get_effective_settings().download_path_template
    return base / apply_path_template(template, dt, filename, source="icloud")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_response(response: Any, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if response is None:
        raise ValueError("Download returned no data")
    if hasattr(response, "raw"):
        with dest.open("wb") as f:
            shutil.copyfileobj(response.raw, f)
    elif hasattr(response, "read"):
        with dest.open("wb") as f:
            shutil.copyfileobj(response, f)
    else:
        with dest.open("wb") as f:
            f.write(response)


def _download_asset(photo: Any, dest: Path) -> None:
    response = download_version(photo, "original")
    _write_response(response, dest)


def _download_live_companion(api_photo: Any, base_dir: Path, primary_filename: str) -> Path | None:
    if not has_live_video_component(api_photo):
        return None
    companion_name = live_video_filename(primary_filename, master_fields(api_photo))
    dest = _local_path(base_dir, api_photo, companion_name)
    if not download_by_prefix(api_photo, LIVE_VIDEO_PREFIX, dest):
        return None
    return dest


class PhotoSyncEngine:
    def __init__(self, db: Session, notifier: Any | None = None, max_workers: int | None = None):
        self.db = db
        self.notifier = notifier
        self.settings = get_settings()
        self.max_workers = max_workers

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
                account_label=account_label(user),
                source=PhotoSource.icloud.value,
                scope=sync_run.scope.value if sync_run else None,
                sync_run_id=sync_run.id if sync_run else None,
                payload=payload,
            )
        )
        if self.notifier and event_type == "sync.completed":
            immich_notify = getattr(self.notifier, "immich_after_sync", None)
            if immich_notify and sync_run and sync_run.scope.value != "all":
                try:
                    immich_notify(user, payload)
                except Exception:
                    logger.exception("Immich notify failed")
        if self.notifier:
            self._notify_daemon_status(event_type, user, payload)

    def _notify_daemon_status(self, event_type: str, user: User, payload: dict):
        if not self.notifier:
            return
        try:
            if event_type == "sync.started":
                self.notifier.sync_started(user)
            elif event_type == "sync.completed":
                self.notifier.sync_completed(user, payload)
            elif event_type == "sync.failed":
                self.notifier.sync_failed(user, payload.get("error", "unknown"))
        except Exception:
            logger.exception("Daemon status notify failed")

    def _photo_exists(self, user_id: int, asset_id: str) -> Photo | None:
        return self.db.scalar(
            select(Photo).where(
                Photo.user_id == user_id,
                Photo.source == PhotoSource.icloud,
                Photo.provider_asset_id == asset_id,
            )
        )

    def _pending_photos(self, user_id: int) -> list[Photo]:
        return list(
            self.db.scalars(
                select(Photo).where(
                    Photo.user_id == user_id,
                    Photo.source == PhotoSource.icloud,
                    Photo.status.in_([PhotoStatus.pending, PhotoStatus.failed]),
                )
            ).all()
        )

    def _is_fully_downloaded(self, record: Photo, api_photo: Any) -> bool:
        if record.status != PhotoStatus.downloaded:
            return False
        if not record.local_path or not Path(record.local_path).exists():
            return False
        if has_live_video_component(api_photo):
            if not record.companion_local_path or not Path(record.companion_local_path).exists():
                return False
        return True

    def _process_photo(
        self,
        user: User,
        api_photo: Any,
        base_dir: Path,
        counters: dict[str, int],
    ) -> str:
        asset_id = _asset_id(api_photo)
        filename = _asset_filename(api_photo)
        existing = self._photo_exists(user.id, asset_id)

        media = asset_media_type(api_photo) or classify_media_type(api_photo)

        if existing and self._is_fully_downloaded(existing, api_photo):
            counters["skipped"] += 1
            return "skipped"

        dest = _local_path(base_dir, api_photo, filename)
        record = existing or Photo(
            user_id=user.id,
            source=PhotoSource.icloud,
            provider_asset_id=asset_id,
            filename=filename,
            status=PhotoStatus.pending,
            asset_date=_asset_date(api_photo),
            media_type=media,
        )
        record.filename = filename
        record.asset_date = _asset_date(api_photo)
        record.media_type = media
        if not existing:
            self.db.add(record)

        try:
            _download_asset(api_photo, dest)
            checksum = _sha256(dest)
            record.local_path = str(dest)
            record.file_size = dest.stat().st_size
            record.checksum_sha256 = checksum
            companion_dest = _download_live_companion(api_photo, base_dir, filename)
            if companion_dest:
                record.companion_local_path = str(companion_dest)
                record.companion_media_type = "live_video"
                record.companion_file_size = companion_dest.stat().st_size
                record.companion_checksum_sha256 = _sha256(companion_dest)
            elif media == "live_photo":
                raise ValueError("Live Photo video component download failed")
            else:
                record.companion_local_path = None
                record.companion_media_type = None
                record.companion_file_size = None
                record.companion_checksum_sha256 = None
            record.status = PhotoStatus.downloaded
            record.downloaded_at = datetime.now(timezone.utc)
            record.error_message = None
            counters["downloaded"] += 1
            return "downloaded"
        except Exception as e:
            record.status = PhotoStatus.failed
            record.error_message = str(e)
            counters["failed"] += 1
            logger.exception("Failed to download %s for user %s", asset_id, account_label(user))
            return "failed"

    def _iter_photos(self, api) -> list[Any]:
        return list_library_photos(api)

    def execute_sync(
        self,
        user: User,
        password: str | None = None,
        sync_run_id: int | None = None,
    ) -> ProviderSyncResult:
        """Download iCloud photos; does not create or finalize a SyncRun row."""
        counters = {"discovered": 0, "downloaded": 0, "failed": 0, "skipped": 0}
        try:
            if is_sync_cancel_requested(self.db, sync_run_id):
                return ProviderSyncResult(
                    source=PhotoSource.icloud,
                    success=False,
                    cancelled=True,
                    error="cancelled",
                )
            cookie_dir = cookie_dir_for_user(user.id)
            api = get_pyicloud_service(user, password=password, cookie_directory=cookie_dir)
            base_dir = provider_download_dir(user, PhotoSource.icloud)

            photos = self._iter_photos(api)
            api_ids = {_asset_id(p) for p in photos}
            counters["discovered"] = len(photos)

            for stale in self._pending_photos(user.id):
                if stale.provider_asset_id not in api_ids:
                    stale.status = PhotoStatus.skipped
                    stale.error_message = "Asset no longer in iCloud library"

            workers = self.max_workers or get_effective_settings().max_concurrent_downloads
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(self._process_photo, user, p, base_dir, counters): p for p in photos
                }
                progress = {"done": 0}

                def on_progress() -> None:
                    progress["done"] += 1
                    if progress["done"] % 10 == 0:
                        self.db.commit()

                stopped = drain_futures_with_cancel(
                    self.db, sync_run_id, futures, on_progress=on_progress
                )
                self.db.commit()
                if stopped:
                    return ProviderSyncResult(
                        source=PhotoSource.icloud,
                        photos_discovered=counters["discovered"],
                        photos_downloaded=counters["downloaded"],
                        photos_failed=counters["failed"],
                        photos_skipped=counters["skipped"],
                        success=False,
                        cancelled=True,
                        error="cancelled",
                    )

            cursor = self._get_or_create_cursor(user)
            cursor.cursor_value = f"synced_{datetime.now(timezone.utc).isoformat()}"
            cursor.updated_at = datetime.now(timezone.utc)

            from iclouddownloader.services.auth_service import AuthService

            AuthService(self.db).mark_session_valid(user)
            self.db.commit()

            return ProviderSyncResult(
                source=PhotoSource.icloud,
                photos_discovered=counters["discovered"],
                photos_downloaded=counters["downloaded"],
                photos_failed=counters["failed"],
                photos_skipped=counters["skipped"],
                success=True,
            )

        except AuthRequired:
            from iclouddownloader.services.auth_service import AuthService

            AuthService(self.db).handle_background_auth_required(user)
            self.db.commit()
            return ProviderSyncResult(
                source=PhotoSource.icloud,
                success=False,
                error="auth_required",
            )

        except Exception as e:
            self.db.commit()
            logger.exception("iCloud sync failed for %s", account_label(user))
            return ProviderSyncResult(
                source=PhotoSource.icloud,
                photos_discovered=counters["discovered"],
                photos_downloaded=counters["downloaded"],
                photos_failed=counters["failed"],
                photos_skipped=counters["skipped"],
                success=False,
                error=str(e),
            )

    def run_sync(
        self,
        user: User,
        password: str | None = None,
        sync_run: SyncRun | None = None,
    ) -> SyncRun:
        own_run = sync_run is None
        if own_run:
            from iclouddownloader.db.models import SyncRunScope

            sync_run = SyncRun(
                user_id=user.id,
                status=SyncRunStatus.running,
                scope=SyncRunScope.icloud,
            )
            self.db.add(sync_run)
            self.db.commit()
            self.db.refresh(sync_run)

        self._publish("sync.started", user, sync_run)
        user.last_sync_status = "syncing"
        self.db.commit()

        result = self.execute_sync(user, password=password, sync_run_id=sync_run.id)
        apply_provider_result_to_run(sync_run, result)
        user.last_sync_at = sync_run.finished_at
        if result.cancelled:
            user.last_sync_status = "idle"
        else:
            user.last_sync_status = "completed" if result.success else "failed"
        self.db.commit()

        if result.cancelled:
            self._publish("sync.cancelled", user, sync_run)
        elif result.success:
            self._publish(
                "sync.completed",
                user,
                sync_run,
                downloaded=sync_run.photos_downloaded,
                failed=sync_run.photos_failed,
                skipped=sync_run.photos_skipped,
            )
        else:
            self._publish("sync.failed", user, sync_run, error=result.error or "unknown")

        return sync_run
