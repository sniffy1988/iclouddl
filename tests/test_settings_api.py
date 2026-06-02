import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("WEB_ADMIN_PASSWORD", "test-admin")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from iclouddownloader.api.app import create_app
from iclouddownloader.config import get_settings
from iclouddownloader.db.models import Base

get_settings.cache_clear()

import iclouddownloader.db.session as session_mod

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
session_mod._engine = _test_engine
session_mod._SessionLocal = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)
Base.metadata.create_all(_test_engine)


def _client():
    client = TestClient(create_app())
    client.post("/api/auth/login", json={"password": get_settings().web_admin_password})
    return client


def test_settings_get_and_patch():
    client = _client()
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert "download_path_template" in r.json()

    r = client.patch(
        "/api/settings",
        json={
            "telegram_enabled": True,
            "telegram_bot_token": "123456789:TESTTOKEN",
            "telegram_admin_chat_id": "-1001",
            "download_path_template": "YYYY/MM/DD/{filename}",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["telegram_enabled"] is True
    assert data["telegram_bot_token_set"] is True
    assert data["download_path_template"] == "YYYY/MM/DD/{filename}"
