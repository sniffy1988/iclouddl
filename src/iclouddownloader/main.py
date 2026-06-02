import uvicorn

from iclouddownloader.config import get_settings


def run_web():
    settings = get_settings()
    uvicorn.run(
        "iclouddownloader.api.app:create_app",
        factory=True,
        host=settings.web_host,
        port=settings.web_port,
        reload=False,
    )


if __name__ == "__main__":
    run_web()
