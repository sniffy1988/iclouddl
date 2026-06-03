"""Sync/count/auth events published to Redis for WebSocket fan-out."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

@dataclass
class SyncEvent:
    type: str
    user_id: int | None = None
    apple_id: str | None = None
    account_label: str | None = None
    source: str | None = None
    scope: str | None = None
    sync_run_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventBus:
    """Publish-only facade; subscribers use Redis + WebSocket on the API process."""

    def publish(self, event: SyncEvent) -> None:
        from iclouddownloader.redis.events import publish_event

        publish_event(event)


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
