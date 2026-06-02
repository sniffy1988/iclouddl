from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import Photo, PhotoSource, PhotoStatus, SyncRun, SyncRunScope, SyncRunStatus, User
from iclouddownloader.events import SyncEvent, get_event_bus
from iclouddownloader.google.client import GooglePhotosClient
from iclouddownloader.path_template import apply_path_template
from iclouddownloader.providers.base import ProviderSyncResult, account_label
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
        if record.status == PhotoStatus.downloaded:
            if record.local_path and Path(record.local_path).exists():
                counters["skipped"] += 1
                return "skipped"

        item = item_cache.get(record.provider_asset_id)
        if not item:
            counters["failed"] += 1
            record.status = PhotoStatus.failed
            record.error_message = "Media item not found in Google library"
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

        try:
            data = client.download_bytes(base_url, variant=variant)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            record.local_path = str(dest)
            record.file_size = dest.stat().st_size
            record.checksum_sha256 = _sha256(dest)
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
        return cache

    def execute_sync(self, user: User) -> ProviderSyncResult:
        counters = {"discovered": 0, "downloaded": 0, "failed": 0, "skipped": 0}
        try:
            base_dir = Path(user.download_dir)
            base_dir.mkdir(parents=True, exist_ok=True)
            pending = self._pending_photos(user.id)
            counters["discovered"] = len(pending)

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
                done = 0
                for future in as_completed(futures):
                    future.result()
                    done += 1
                    if done % 10 == 0:
                        self.db.commit()

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

    def _apply_result_to_run(self, sync_run: SyncRun, result: ProviderSyncResult) -> None:
        sync_run.photos_discovered = result.photos_discovered
        sync_run.photos_downloaded = result.photos_downloaded
        sync_run.photos_failed = result.photos_failed
        sync_run.photos_skipped = result.photos_skipped
        if result.success:
            sync_run.status = SyncRunStatus.completed
            sync_run.error_summary = None
        else:
            sync_run.status = SyncRunStatus.failed
            sync_run.error_summary = result.error
        sync_run.finished_at = datetime.now(timezone.utc)

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
        result = self.execute_sync(user)
        self._apply_result_to_run(sync_run, result)
        user.last_sync_at = sync_run.finished_at
        user.last_sync_status = "completed" if result.success else "failed"
        self.db.commit()

        if result.success:
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
