"""Shared test DB and admin bootstrap helper."""

from __future__ import annotations

import os
import tempfile

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["BASE_DOWNLOAD_DIR"] = _tmp
os.environ["COOKIE_DIR"] = _tmp + "/cookies"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"

from iclouddownloader.api.app import create_app  # noqa: E402
from iclouddownloader.config import get_settings  # noqa: E402
from iclouddownloader.db.models import Base  # noqa: E402

get_settings.cache_clear()

import iclouddownloader.db.session as session_mod  # noqa: E402

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
session_mod._engine = _test_engine
session_mod._SessionLocal = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)
Base.metadata.create_all(_test_engine)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    import iclouddownloader.redis.client as redis_client

    events_server = fakeredis.FakeStrictRedis(decode_responses=True)
    rq_server = fakeredis.FakeStrictRedis(decode_responses=False)
    monkeypatch.setattr(redis_client, "_client", events_server)
    monkeypatch.setattr(redis_client, "_subscriber_client", events_server)
    monkeypatch.setattr(redis_client, "_rq_client", rq_server)
    monkeypatch.setattr(redis_client, "get_redis", lambda: events_server)
    monkeypatch.setattr(redis_client, "get_redis_subscriber", lambda: events_server)
    monkeypatch.setattr(redis_client, "get_rq_redis", lambda: rq_server)
    yield events_server
    redis_client._client = None
    redis_client._subscriber_client = None
    redis_client._rq_client = None


@pytest.fixture
def db_session():
    session = session_mod._SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def login_test_admin(client: TestClient, password: str = "test-admin-pass") -> None:
    status = client.get("/api/auth/status").json()
    if status.get("needs_setup"):
        r = client.post("/api/auth/setup", json={"password": password})
        assert r.status_code == 200, r.text
    else:
        r = client.post("/api/auth/login", json={"password": password})
        assert r.status_code == 200, r.text
