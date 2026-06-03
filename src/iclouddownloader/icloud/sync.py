from __future__ import annotations

import hashlib
import logging
import shutil
import threading
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
    download_asset_to_file,
    download_by_prefix,
    has_live_video_component,
    is_stale_download_url_error,
    live_video_filename,
    master_fields,
)
from iclouddownloader.paths import provider_download_dir
from iclouddownloader.providers.base import ProviderSyncResult, account_label, apply_provider_result_to_run
from iclouddownloader.providers.cancel import drain_futures_with_cancel, is_sync_cancel_requested
from iclouddownloader.providers.local_files import (
    mark_photo_missing_on_disk,
    photo_files_on_disk,
    reconcile_stale_downloads,
    try_adopt_existing_on_disk,
    verify_written_file,
)
from iclouddownloader.providers.sync_progress import (
    publish_sync_progress,
    should_report_sync_progress,
)

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

    @staticmethod
    def _merge_counter_delta(counters: dict[str, int], delta: dict[str, int] | None) -> None:
        if not delta:
            counters["failed"] += 1
            return
        for key in ("downloaded", "failed", "skipped"):
            counters[key] += int(delta.get(key, 0))

    @staticmethod
    def process_photo_in_worker(
        user_id: int,
        api_photo: Any,
        base_dir: Path,
    ) -> dict[str, int]:
        """Download one asset using a dedicated DB session (thread-safe)."""
        from iclouddownloader.db.session import get_session_factory

        db = get_session_factory()()
        delta = {"downloaded": 0, "failed": 0, "skipped": 0}
        try:
            user = db.get(User, user_id)
            if not user:
                delta["failed"] += 1
                return delta
            PhotoSyncEngine(db)._process_photo(user, api_photo, base_dir, delta)
            db.commit()
            return delta
        except Exception:
            db.rollback()
            delta["failed"] += 1
            logger.exception("iCloud download worker failed for user %s", user_id)
            return delta
        finally:
            db.close()

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

    def _is_fully_downloaded(
        self, record: Photo, api_photo: Any, *, require_live_companion: bool
    ) -> bool:
        if record.status != PhotoStatus.downloaded:
            return False
        if photo_files_on_disk(record, require_companion=require_live_companion):
            return True
        mark_photo_missing_on_disk(record)
        return False

    def _process_photo(
        self,
        user: User,
        api_photo: Any,
        base_dir: Path,
        counters: dict[str, int],
    ) -> str:
        effective = get_effective_settings()
        asset_id = _asset_id(api_photo)
        filename = _asset_filename(api_photo)
        existing = self._photo_exists(user.id, asset_id)

        media = asset_media_type(api_photo) or classify_media_type(api_photo)
        require_live = has_live_video_component(api_photo) and not effective.skip_live_companions

        if effective.skip_videos and media == "video":
            record = existing or Photo(
                user_id=user.id,
                source=PhotoSource.icloud,
                provider_asset_id=asset_id,
                filename=filename,
                status=PhotoStatus.skipped,
                asset_date=_asset_date(api_photo),
                media_type=media,
                error_message="Skipped by settings (videos disabled)",
            )
            if not existing:
                self.db.add(record)
            else:
                record.status = PhotoStatus.skipped
                record.error_message = "Skipped by settings (videos disabled)"
            counters["skipped"] += 1
            return "skipped"

        if existing and self._is_fully_downloaded(existing, api_photo, require_live_companion=require_live):
            counters["skipped"] += 1
            return "skipped"

        dest = _local_path(base_dir, api_photo, filename)
        companion_dest = None
        if require_live:
            companion_dest = _local_path(
                base_dir, api_photo, live_video_filename(filename, master_fields(api_photo))
            )
        version = effective.icloud_download_version if effective.icloud_download_version in (
            "original",
            "medium",
        ) else "original"
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

        if try_adopt_existing_on_disk(
            record,
            dest,
            companion=companion_dest,
            require_companion=require_live,
            companion_media_type="live_video" if require_live else None,
            checksum_fn=_sha256,
        ):
            counters["skipped"] += 1
            return "skipped"

        try:
            download_asset_to_file(api_photo, dest, version=version)
            verify_written_file(dest)
            checksum = _sha256(dest)
            record.local_path = str(dest.resolve())
            record.file_size = dest.stat().st_size
            record.checksum_sha256 = checksum
            if require_live:
                companion_dest = _download_live_companion(api_photo, base_dir, filename)
            else:
                companion_dest = None
            if companion_dest:
                verify_written_file(companion_dest)
                record.companion_local_path = str(companion_dest.resolve())
                record.companion_media_type = "live_video"
                record.companion_file_size = companion_dest.stat().st_size
                record.companion_checksum_sha256 = _sha256(companion_dest)
            elif require_live:
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
            if is_stale_download_url_error(e):
                logger.warning(
                    "iCloud download URL expired for %s (user %s): %s",
                    asset_id,
                    account_label(user),
                    e,
                )
            else:
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

            reconcile_stale_downloads(self.db, user.id, source=PhotoSource.icloud)

            for stale in self._pending_photos(user.id):
                if stale.provider_asset_id not in api_ids:
                    stale.status = PhotoStatus.skipped
                    stale.error_message = "Asset no longer in iCloud library"

            from iclouddownloader.config import get_settings
            from iclouddownloader.db.session import sqlite_file_path

            use_sequential = bool(sqlite_file_path(get_settings().database_url))
            if use_sequential:
                logger.info(
                    "Sequential iCloud downloads for user %s (%s assets; SQLite-safe)",
                    user.id,
                    len(photos),
                )
                for i, photo in enumerate(photos):
                    if is_sync_cancel_requested(self.db, sync_run_id):
                        self.db.commit()
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
                    self._process_photo(user, photo, base_dir, counters)
                    done = i + 1
                    if should_report_sync_progress(done):
                        self.db.commit()
                        publish_sync_progress(
                            self.db,
                            user,
                            sync_run_id,
                            counters,
                            source=PhotoSource.icloud,
                        )
                self.db.commit()
            else:
                workers = self.max_workers or get_effective_settings().max_concurrent_downloads
                counter_lock = threading.Lock()

                def merge_delta(delta: dict[str, int] | None, *, error: Exception | None = None) -> None:
                    with counter_lock:
                        if error is not None:
                            counters["failed"] += 1
                        else:
                            PhotoSyncEngine._merge_counter_delta(counters, delta)

                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {
                        pool.submit(
                            PhotoSyncEngine.process_photo_in_worker,
                            user.id,
                            p,
                            base_dir,
                        ): p
                        for p in photos
                    }
                    progress = {"done": 0}

                    def on_progress() -> None:
                        progress["done"] += 1
                        done = progress["done"]
                        if should_report_sync_progress(done):
                            with counter_lock:
                                snap = dict(counters)
                            publish_sync_progress(
                                self.db,
                                user,
                                sync_run_id,
                                snap,
                                source=PhotoSource.icloud,
                            )

                    stopped = drain_futures_with_cancel(
                        self.db,
                        sync_run_id,
                        futures,
                        on_progress=on_progress,
                        on_future_done=lambda result, error=None: merge_delta(
                            result if error is None else None, error=error
                        ),
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
