import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite://"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from iclouddownloader.db.models import AuthChallenge, AuthChallengeStatus, AuthChallengeType, Base, User
from iclouddownloader.icloud.auth import AuthRequired
from iclouddownloader.services.auth_service import AuthService

import iclouddownloader.db.session as session_mod

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
session_mod._engine = _test_engine
session_mod._SessionLocal = sessionmaker(bind=_test_engine, autocommit=False, autoflush=False)
Base.metadata.create_all(_test_engine)


def _user_and_challenge(db):
    user = User(
        apple_id="test@icloud.com",
        download_dir=_tmp,
        sync_interval_seconds=3600,
        icloud_needs_auth=True,
    )
    db.add(user)
    db.flush()
    challenge = AuthChallenge(
        user_id=user.id,
        challenge_type=AuthChallengeType.twofa,
        status=AuthChallengeStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.add(challenge)
    db.commit()
    return user, challenge


@patch("iclouddownloader.services.auth_service.submit_2fa_code", return_value=True)
@patch("iclouddownloader.services.auth_service.get_pyicloud_service")
def test_submit_uses_cookie_session_first(mock_get, mock_submit):
    db = session_mod._SessionLocal()
    user, challenge = _user_and_challenge(db)
    mock_api = MagicMock()
    mock_get.side_effect = [
        AuthRequired(AuthChallengeType.twofa, mock_api),
    ]

    result = AuthService(db).submit_challenge_code(
        user.id, "844632", challenge.id, password="secret"
    )

    assert result.status == AuthChallengeStatus.completed
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs.get("password") is None
    mock_submit.assert_called_once_with(mock_api, "844632")
