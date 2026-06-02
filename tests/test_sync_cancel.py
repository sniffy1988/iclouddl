from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import login_test_admin
from iclouddownloader.db.models import SyncRun, SyncRunScope, SyncRunStatus, User
from iclouddownloader.providers.cancel import is_sync_cancel_requested
from iclouddownloader.services.sync_service import SyncService


def test_request_cancel_sets_flag(client: TestClient, db_session: Session):
    login_test_admin(client)
    user = User(apple_id="cancel@test.com", download_dir="/tmp/c")
    db_session.add(user)
    db_session.flush()
    run = SyncRun(
        user_id=user.id,
        status=SyncRunStatus.running,
        scope=SyncRunScope.icloud,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    user.last_sync_status = "syncing"
    db_session.commit()

    r = client.post(f"/api/users/{user.id}/sync/cancel?source=icloud")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert run.id in body["cancelled_run_ids"]

    db_session.refresh(run)
    assert run.cancel_requested is True
    assert is_sync_cancel_requested(db_session, run.id) is True


def test_request_cancel_clears_queued(client: TestClient, db_session: Session):
    login_test_admin(client)
    user = User(apple_id="queued@test.com", download_dir="/tmp/q")
    db_session.add(user)
    user.last_sync_status = "queued"
    db_session.commit()

    r = client.post(f"/api/users/{user.id}/sync/cancel")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    db_session.refresh(user)
    assert user.last_sync_status == "idle"


def test_apply_cancelled_result(db_session: Session):
    user = User(apple_id="a@b.com", download_dir="/tmp")
    db_session.add(user)
    db_session.flush()
    run = SyncRun(user_id=user.id, status=SyncRunStatus.running, scope=SyncRunScope.icloud)
    db_session.add(run)
    db_session.commit()

    from iclouddownloader.providers.base import ProviderSyncResult, apply_provider_result_to_run
    from iclouddownloader.db.models import PhotoSource

    apply_provider_result_to_run(
        run,
        ProviderSyncResult(PhotoSource.icloud, photos_downloaded=3, success=False, cancelled=True),
    )
    db_session.commit()
    db_session.refresh(run)
    assert run.status == SyncRunStatus.cancelled
    assert run.cancel_requested is False
    assert run.photos_downloaded == 3
