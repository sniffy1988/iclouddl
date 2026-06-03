from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import asdict
from functools import partial

from iclouddownloader.config import get_settings
from iclouddownloader.events import SyncEvent
from iclouddownloader.redis.client import get_redis, get_redis_subscriber

logger = logging.getLogger(__name__)


def publish_event(event: SyncEvent) -> None:
    channel = get_settings().redis_events_channel
    payload = json.dumps(asdict(event), default=str)
    receivers = get_redis().publish(channel, payload)
    indexed = (event.payload or {}).get("indexed")
    if receivers == 0:
        logger.warning(
            "Published %s but no Redis subscribers on %s (is the API process running?)",
            event.type,
            channel,
        )
    elif event.type.startswith("count.") or event.type == "sync.progress":
        extra = (event.payload or {}).get("indexed")
        if event.type == "sync.progress":
            extra = (event.payload or {}).get("downloaded")
        logger.info(
            "Redis publish %s user=%s progress=%s (%s subscriber(s))",
            event.type,
            event.user_id,
            extra,
            receivers,
        )
    else:
        logger.debug("Published %s to %s (%s subscriber(s))", event.type, channel, receivers)


async def subscribe_events_async(
    stop_event: asyncio.Event | None = None,
) -> AsyncIterator[SyncEvent]:
    """Async generator yielding SyncEvent from Redis pub/sub."""
    channel = get_settings().redis_events_channel
    client = get_redis_subscriber()
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)
    logger.info("Redis events bridge subscribed to %s", channel)

    loop = asyncio.get_running_loop()
    get_message = partial(pubsub.get_message, timeout=1.0)

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            msg = await loop.run_in_executor(None, get_message)
            if msg is None:
                await asyncio.sleep(0.05)
                continue
            if msg.get("type") != "message":
                continue
            data = msg.get("data")
            if not data:
                continue
            try:
                raw = json.loads(data)
                if raw.get("payload") is None:
                    raw["payload"] = {}
                yield SyncEvent(**raw)
            except Exception:
                logger.warning("Invalid event payload on %s", channel, exc_info=True)
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:
            pass
        logger.info("Redis events subscriber closed")
