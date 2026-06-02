"""In-process event bus for SSE live sync updates."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
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

    def to_sse(self) -> str:
        data = asdict(self)
        return f"event: {self.type}\ndata: {json.dumps(data)}\n\n"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[SyncEvent]] = []

    def publish(self, event: SyncEvent) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def subscribe(self) -> AsyncIterator[SyncEvent]:
        queue: asyncio.Queue[SyncEvent] = asyncio.Queue(maxsize=256)
        self._subscribers.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
