import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from iclouddownloader.api.routes import auth, google_auth, logs, photos, settings, sync, users, ws
from iclouddownloader.api.realtime import redis_events_bridge
from iclouddownloader.redis.client import ping_redis
from iclouddownloader.api.web_static import safe_dist_file
from iclouddownloader.logging_setup import (
    configure_logging,
    get_logging_level,
    should_log_http_requests,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(force=True)
    stop = asyncio.Event()
    bridge = asyncio.create_task(redis_events_bridge(stop))
    try:
        yield
    finally:
        stop.set()
        bridge.cancel()
        try:
            await bridge
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    app = FastAPI(title="iCloud Photo Downloader", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        if not should_log_http_requests():
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s (%.0f ms)",
            request.method,
            request.url.path,
            response.status_code,
            ms,
        )
        return response

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(google_auth.router)
    app.include_router(photos.router)
    app.include_router(sync.router)
    app.include_router(settings.router)
    app.include_router(logs.router)
    app.include_router(ws.router)

    @app.get("/api/health")
    def health():
        redis_ok = ping_redis()
        return {
            "status": "ok" if redis_ok else "degraded",
            "redis": redis_ok,
            "logging_level": get_logging_level(),
            "debug_logging_enabled": get_logging_level() == "DEBUG",
        }

    web_dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    if web_dist.exists():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            if full_path.startswith("api"):
                from fastapi import HTTPException

                raise HTTPException(404)
            static = safe_dist_file(web_dist, full_path) if full_path else None
            if static is not None:
                return FileResponse(static)
            index = web_dist / "index.html"
            if index.exists():
                return FileResponse(index)
            return {"message": "Web UI not built. Run: cd web && npm run build"}

    return app
