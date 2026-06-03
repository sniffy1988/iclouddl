from __future__ import annotations

import logging

import redis
from redis import Redis

from iclouddownloader.config import get_settings

logger = logging.getLogger(__name__)

_client: Redis | None = None
_subscriber_client: Redis | None = None
_rq_client: Redis | None = None


def _redis_url() -> str:
    return get_settings().redis_url


def get_redis() -> Redis:
    """Text mode for publishing JSON events (decode_responses=True)."""
    global _client
    if _client is None:
        _client = redis.from_url(_redis_url(), decode_responses=True)
    return _client


def get_redis_subscriber() -> Redis:
    """Dedicated connection for pub/sub listen (do not share with publish)."""
    global _subscriber_client
    if _subscriber_client is None:
        _subscriber_client = redis.from_url(_redis_url(), decode_responses=True)
    return _subscriber_client


def get_rq_redis() -> Redis:
    """Binary mode for RQ job payloads (must not decode pickled job data)."""
    global _rq_client
    if _rq_client is None:
        _rq_client = redis.from_url(_redis_url(), decode_responses=False)
    return _rq_client


def ping_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        logger.debug("Redis ping failed", exc_info=True)
        return False
