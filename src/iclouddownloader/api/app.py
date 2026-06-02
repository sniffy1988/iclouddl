from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from iclouddownloader.api.routes import auth, photos, settings, sync, users


def create_app() -> FastAPI:
    app = FastAPI(title="iCloud Photo Downloader", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(photos.router)
    app.include_router(sync.router)
    app.include_router(settings.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    web_dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    if web_dist.exists():
        app.mount("/assets", StaticFiles(directory=web_dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            if full_path.startswith("api"):
                from fastapi import HTTPException

                raise HTTPException(404)
            index = web_dist / "index.html"
            if index.exists():
                return FileResponse(index)
            return {"message": "Web UI not built. Run: cd web && npm run build"}

    return app
