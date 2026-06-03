from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from iclouddownloader.api.deps import SESSION_COOKIE, session_valid
from iclouddownloader.api.realtime import get_connection_manager, send_ws_welcome
from iclouddownloader.db.session import get_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])


@router.websocket("/api/ws")
async def websocket_events(websocket: WebSocket):
    token = websocket.cookies.get(SESSION_COOKIE)
    db: Session = get_session_factory()()
    try:
        if not session_valid(db, token):
            await websocket.close(code=4401)
            return
    finally:
        db.close()

    manager = get_connection_manager()
    await manager.connect(websocket)
    await send_ws_welcome(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
