from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict

from fastapi import WebSocket, WebSocketDisconnect

from iclouddownloader.events import SyncEvent

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
            logger.info("WebSocket client connected (%s total)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
            logger.info("WebSocket client disconnected (%s total)", len(self._connections))

    async def broadcast(self, event: SyncEvent) -> None:
        payload = json.dumps(asdict(event), default=str)
        async with self._lock:
            if not self._connections:
                logger.debug("No WebSocket clients for %s", event.type)
                return
            dead: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                if ws in self._connections:
                    self._connections.remove(ws)
            if event.type.startswith("count.") or event.type == "sync.progress":
                progress_val = (event.payload or {}).get("indexed")
                if event.type == "sync.progress":
                    progress_val = (event.payload or {}).get("downloaded")
                logger.info(
                    "WebSocket broadcast %s user=%s progress=%s (%s client(s))",
                    event.type,
                    event.user_id,
                    progress_val,
                    len(self._connections),
                )
            else:
                logger.debug(
                    "Broadcast %s to %s client(s)",
                    event.type,
                    len(self._connections),
                )


_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


async def redis_events_bridge(stop_event: asyncio.Event) -> None:
    from iclouddownloader.redis.events import subscribe_events_async

    manager = get_connection_manager()
    try:
        async for event in subscribe_events_async(stop_event):
            await manager.broadcast(event)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Redis events bridge stopped")
    finally:
        logger.info("Redis events bridge exited")


async def send_ws_welcome(websocket: WebSocket) -> None:
    """So clients / DevTools see traffic immediately after connect."""
    await websocket.send_text(
        json.dumps(
            {
                "type": "realtime.connected",
                "payload": {},
                "timestamp": "",
            }
        )
    )
