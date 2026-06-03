from __future__ import annotations

import json

from iclouddownloader.config import get_settings
from iclouddownloader.events import SyncEvent, get_event_bus
from iclouddownloader.redis import client as redis_client
from iclouddownloader.redis.events import publish_event


def test_publish_event_uses_redis_channel():
    published: list[tuple[str, str]] = []

    def capture(channel: str, payload: str) -> int:
        published.append((channel, payload))
        return 1

    redis = redis_client.get_redis()
    redis.publish = capture  # type: ignore[method-assign]

    event = SyncEvent(type="sync.started", user_id=1, apple_id="a@b.com")
    publish_event(event)

    assert len(published) == 1
    channel, raw = published[0]
    assert channel == get_settings().redis_events_channel
    data = json.loads(raw)
    assert data["type"] == "sync.started"
    assert data["user_id"] == 1


def test_event_bus_publishes_to_redis():
    published: list[str] = []

    def capture(channel: str, payload: str) -> int:
        published.append(payload)
        return 1

    redis_client.get_redis().publish = capture  # type: ignore[method-assign]

    get_event_bus().publish(SyncEvent(type="count.progress", user_id=2, payload={"indexed": 10}))

    data = json.loads(published[0])
    assert data["type"] == "count.progress"
    assert data["payload"]["indexed"] == 10
