from __future__ import annotations

from redis import Redis
from rq import Queue

from iclouddownloader.config import get_settings
from iclouddownloader.db.models import PhotoSource
from iclouddownloader.jobs.tasks import JOB_TIMEOUT, task_fetch_photo_count, task_trigger_sync
from iclouddownloader.redis.client import get_rq_redis

_sync_queue: Queue | None = None
_count_queue: Queue | None = None


def _connection() -> Redis:
    return get_rq_redis()


def sync_queue() -> Queue:
    global _sync_queue
    if _sync_queue is None:
        settings = get_settings()
        _sync_queue = Queue(
            settings.rq_sync_queue,
            connection=_connection(),
            default_timeout=JOB_TIMEOUT,
        )
    return _sync_queue


def count_queue() -> Queue:
    global _count_queue
    if _count_queue is None:
        settings = get_settings()
        _count_queue = Queue(
            settings.rq_count_queue,
            connection=_connection(),
            default_timeout=JOB_TIMEOUT,
        )
    return _count_queue


def enqueue_count(user_id: int, source: PhotoSource) -> None:
    count_queue().enqueue(
        task_fetch_photo_count,
        user_id,
        source.value,
        job_timeout=JOB_TIMEOUT,
        result_ttl=0,
        failure_ttl=86400,
    )


def enqueue_sync(user_id: int, source: PhotoSource | None = None) -> None:
    sync_queue().enqueue(
        task_trigger_sync,
        user_id,
        source.value if source else None,
        job_timeout=JOB_TIMEOUT,
        result_ttl=0,
        failure_ttl=86400,
    )
