from iclouddownloader.db.models import PhotoSource, User
from iclouddownloader.services.sync_service import SyncService


def test_event_count_completed_with_photo_count_result(db_session):
    user = User(apple_id="event@test.com", download_dir="/tmp/e")
    db_session.add(user)
    db_session.commit()

    svc = SyncService(db_session)
    result = svc.build_photo_count_result(user, PhotoSource.icloud)
    assert "source" in result

    # Must not raise: result["source"] collides with _event photo_source param name
    svc._event(user, "count.completed", PhotoSource.icloud, **result)
