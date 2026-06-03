import pytest
from unittest.mock import patch

from iclouddownloader.db.models import PhotoSource, SyncRun, SyncRunScope, SyncRunStatus, User
from iclouddownloader.services.sync_service import SyncInProgressError, SyncService
from conftest import login_test_admin


def test_create_user_without_apple_id(client, db_session):
    login_test_admin(client)
    r = client.post("/api/users?fetch_count=false", json={"display_name": "Google Only"})
    assert r.status_code == 201
    body = r.json()
    assert body["apple_id"] is None
    assert body["display_name"] == "Google Only"


def test_scope_conflict_blocks_same_provider(client, db_session):
    login_test_admin(client)
    user = User(
        apple_id="scope@icloud.com",
        display_name="scope",
        download_dir="/tmp/scope",
        enabled=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    run = SyncRun(user_id=user.id, status=SyncRunStatus.running, scope=SyncRunScope.icloud)
    db_session.add(run)
    db_session.commit()

    svc = SyncService(db_session)
    with pytest.raises(SyncInProgressError) as exc:
        svc.ensure_can_start_sync(user.id, requested=PhotoSource.icloud)
    assert exc.value.scope == "icloud"


def test_concurrent_different_providers_allowed(client, db_session):
    login_test_admin(client)
    user = User(
        apple_id="dual@icloud.com",
        display_name="dual",
        download_dir="/tmp/dual",
        enabled=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    run = SyncRun(user_id=user.id, status=SyncRunStatus.running, scope=SyncRunScope.icloud)
    db_session.add(run)
    db_session.commit()

    svc = SyncService(db_session)
    svc.ensure_can_start_sync(user.id, requested=PhotoSource.google_photos)


def test_trigger_sync_passes_source_query(client, db_session):
    login_test_admin(client)
    user = User(
        apple_id="syncq@icloud.com",
        display_name="syncq",
        download_dir="/tmp/syncq",
        enabled=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    with patch("iclouddownloader.api.routes.users.enqueue_sync") as mock_enqueue:
        r = client.post(f"/api/users/{user.id}/sync?source=icloud")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["source"] == "icloud"
        mock_enqueue.assert_called_once_with(user.id, PhotoSource.icloud)
