from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import Photo, PhotoSource, PhotoStatus, SyncRun, SyncRunScope, SyncRunStatus, User
from iclouddownloader.events import SyncEvent, get_event_bus
from iclouddownloader.google.assets import is_motion_photo, media_item_ready
from iclouddownloader.google.client import GooglePhotosClient
from iclouddownloader.path_template import apply_path_template
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
from iclouddownloader.services.runtime_settings_service import get_effective_settings

logger = logging.getLogger(__name__)


def _local_path(
    base: Path,
    dt: datetime,
    filename: str,
    path_template: str | None = None,
) -> Path:
    template = path_template or get_effective_settings().download_path_template
    return base / apply_path_template(template, dt, filename, source="google_photos")


def _motion_companion_filename(primary_filename: str) -> str:
    stem = Path(primary_filename).stem
    return f"{stem}.mp4"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class GooglePhotoSyncEngine:
    def __init__(self, db: Session, notifier: Any | None = None, max_workers: int | None = None):
        self.db = db
        self.notifier = notifier
        self.max_workers = max_workers

    def _publish(self, event_type: str, user: User, sync_run: SyncRun | None = None, **payload):
        get_event_bus().publish(
            SyncEvent(
                type=event_type,
                user_id=user.id,
                apple_id=user.apple_id,
                account_label=account_label(user),
                source=PhotoSource.google_photos.value,
                scope=sync_run.scope.value if sync_run else None,
                sync_run_id=sync_run.id if sync_run else None,
                payload=payload,
            )
        )
        if self.notifier:
            self._notify_daemon_status(event_type, user, payload)

    def _notify_daemon_status(self, event_type: str, user: User, payload: dict):
        try:
            if event_type == "sync.started":
                self.notifier.sync_started(user)
            elif event_type == "sync.completed":
                self.notifier.sync_completed(user, payload)
            elif event_type == "sync.failed":
                self.notifier.sync_failed(user, payload.get("error", "unknown"))
        except Exception:
            logger.exception("Daemon status notify failed")

    def _pending_photos(self, user_id: int) -> list[Photo]:
        return list(
            self.db.scalars(
                select(Photo).where(
                    Photo.user_id == user_id,
                    Photo.source == PhotoSource.google_photos,
                    Photo.status.in_([PhotoStatus.pending, PhotoStatus.failed]),
                )
            ).all()
        )

    def _download_record(
        self,
        user: User,
        record: Photo,
        client: GooglePhotosClient,
        base_dir: Path,
        counters: dict[str, int],
        item_cache: dict[str, dict],
    ) -> str:
        item = item_cache.get(record.provider_asset_id)
        if not item:
            counters["failed"] += 1
            record.status = PhotoStatus.failed
            record.error_message = "Media item not found in Google library"
            return "failed"

        effective = get_effective_settings()
        motion = is_motion_photo(item)
        require_motion = motion and not effective.skip_motion_companions

        if effective.skip_videos and record.media_type == "video":
            record.status = PhotoStatus.skipped
            record.error_message = "Skipped by settings (videos disabled)"
            counters["skipped"] += 1
            return "skipped"

        if record.status == PhotoStatus.downloaded:
            if photo_files_on_disk(record, require_companion=require_motion):
                counters["skipped"] += 1
                return "skipped"
            mark_photo_missing_on_disk(record)

        if not media_item_ready(item):
            counters["failed"] += 1
            record.status = PhotoStatus.failed
            record.error_message = "Media item not ready for download"
            return "failed"

        base_url = item.get("baseUrl")
        if not base_url:
            counters["failed"] += 1
            record.status = PhotoStatus.failed
            record.error_message = "Missing baseUrl"
            return "failed"

        dt = record.asset_date or datetime.now(timezone.utc)
        dest = _local_path(base_dir, dt, record.filename)
        variant = "dv" if (record.media_type == "video") else "d"
        companion_dest = None
        if require_motion:
            companion_dest = _local_path(base_dir, dt, _motion_companion_filename(record.filename))

        if try_adopt_existing_on_disk(
            record,
            dest,
            companion=companion_dest,
            require_companion=require_motion,
            companion_media_type="motion_video" if require_motion else None,
            checksum_fn=_sha256,
        ):
            counters["skipped"] += 1
            return "skipped"

        try:
            data = client.download_bytes(base_url, variant=variant)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            verify_written_file(dest)
            record.local_path = str(dest.resolve())
            record.file_size = dest.stat().st_size
            record.checksum_sha256 = _sha256(dest)
            if require_motion:
                if companion_dest is None:
                    companion_dest = _local_path(
                        base_dir, dt, _motion_companion_filename(record.filename)
                    )
                video_data = client.download_bytes(base_url, variant="dv")
                companion_dest.parent.mkdir(parents=True, exist_ok=True)
                companion_dest.write_bytes(video_data)
                verify_written_file(companion_dest)
                record.companion_local_path = str(companion_dest.resolve())
                record.companion_media_type = "motion_video"
                record.companion_file_size = companion_dest.stat().st_size
                record.companion_checksum_sha256 = _sha256(companion_dest)
            elif motion and effective.skip_motion_companions:
                record.companion_local_path = None
                record.companion_media_type = None
                record.companion_file_size = None
                record.companion_checksum_sha256 = None
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
            logger.exception("Google download failed for %s", record.provider_asset_id)
            return "failed"

    def _build_item_cache(self, user: User, client: GooglePhotosClient) -> dict[str, dict]:
        cache: dict[str, dict] = {}
        page_token = None
        while True:
            data = client.list_media_items(page_size=100, page_token=page_token)
            for item in data.get("mediaItems") or []:
                cache[str(item["id"])] = item
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        logger.info(
            "Google library cache built for user %s: %s mediaItems",
            user.id,
            len(cache),
        )
        return cache

    def execute_sync(self, user: User, sync_run_id: int | None = None) -> ProviderSyncResult:
        counters = {"discovered": 0, "downloaded": 0, "failed": 0, "skipped": 0}
        try:
            if is_sync_cancel_requested(self.db, sync_run_id):
                return ProviderSyncResult(
                    source=PhotoSource.google_photos,
                    success=False,
                    cancelled=True,
                    error="cancelled",
                )
            base_dir = provider_download_dir(user, PhotoSource.google_photos)
            pending = self._pending_photos(user.id)
            counters["discovered"] = len(pending)

            reconcile_stale_downloads(self.db, user.id, source=PhotoSource.google_photos)

            if not pending:
                return ProviderSyncResult(
                    source=PhotoSource.google_photos,
                    success=True,
                )

            client = GooglePhotosClient.for_user(user)
            item_cache = self._build_item_cache(user, client)
            workers = self.max_workers or get_effective_settings().max_concurrent_downloads

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(
                        self._download_record,
                        user,
                        rec,
                        client,
                        base_dir,
                        counters,
                        item_cache,
                    ): rec
                    for rec in pending
                }
                progress = {"done": 0}

                def on_progress() -> None:
                    progress["done"] += 1
                    done = progress["done"]
                    if should_report_sync_progress(done):
                        self.db.commit()
                        publish_sync_progress(
                            self.db,
                            user,
                            sync_run_id,
                            counters,
                            source=PhotoSource.google_photos,
                        )

                stopped = drain_futures_with_cancel(
                    self.db, sync_run_id, futures, on_progress=on_progress
                )
                self.db.commit()
                if stopped:
                    return ProviderSyncResult(
                        source=PhotoSource.google_photos,
                        photos_discovered=counters["discovered"],
                        photos_downloaded=counters["downloaded"],
                        photos_failed=counters["failed"],
                        photos_skipped=counters["skipped"],
                        success=False,
                        cancelled=True,
                        error="cancelled",
                    )

            self.db.commit()
            return ProviderSyncResult(
                source=PhotoSource.google_photos,
                photos_discovered=counters["discovered"],
                photos_downloaded=counters["downloaded"],
                photos_failed=counters["failed"],
                photos_skipped=counters["skipped"],
                success=True,
            )

        except Exception as e:
            err = str(e)
            if "invalid_grant" in err.lower() or "401" in err:
                user.google_needs_auth = True
            self.db.commit()
            logger.exception("Google sync failed for %s", account_label(user))
            return ProviderSyncResult(
                source=PhotoSource.google_photos,
                photos_discovered=counters["discovered"],
                photos_downloaded=counters["downloaded"],
                photos_failed=counters["failed"],
                photos_skipped=counters["skipped"],
                success=False,
                error=err,
            )

    def run_sync(self, user: User, sync_run: SyncRun | None = None) -> SyncRun:
        own_run = sync_run is None
        if own_run:
            sync_run = SyncRun(
                user_id=user.id,
                status=SyncRunStatus.running,
                scope=SyncRunScope.google_photos,
            )
            self.db.add(sync_run)
            self.db.commit()
            self.db.refresh(sync_run)

        self._publish("sync.started", user, sync_run)
        user.last_sync_status = "syncing"
        self.db.commit()
        result = self.execute_sync(user, sync_run_id=sync_run.id)
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
