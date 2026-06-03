from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from iclouddownloader.db.models import AuthChallenge, AuthChallengeStatus, AuthChallengeType, User
from iclouddownloader.services.user_service import UserService


def test_delete_user_removes_auth_challenges(db_session):
    user = User(
        apple_id="delete-me@icloud.com",
        download_dir="/tmp/dl",
        sync_interval_seconds=3600,
    )
    db_session.add(user)
    db_session.flush()

    challenge = AuthChallenge(
        user_id=user.id,
        challenge_type=AuthChallengeType.twofa,
        status=AuthChallengeStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(challenge)
    db_session.commit()

    UserService(db_session).delete_user(user.id)

    assert db_session.get(User, user.id) is None
    assert (
        db_session.scalar(select(AuthChallenge).where(AuthChallenge.user_id == user.id))
        is None
    )
    assert db_session.scalars(select(AuthChallenge)).all() == []
