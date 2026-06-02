import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from iclouddownloader.admin_auth import (
    admin_configured,
    hash_admin_password,
    verify_admin_password,
)
from iclouddownloader.db.models import RuntimeSettings


def test_admin_configured():
    assert admin_configured(None) is False
    assert admin_configured(RuntimeSettings(id=1, admin_password_hash="")) is False
    row = RuntimeSettings(id=1, admin_password_hash=hash_admin_password("my-secret"))
    assert admin_configured(row) is True
    assert verify_admin_password("my-secret", row) is True
    assert verify_admin_password("wrong", row) is False


def test_verify_fails_when_not_configured():
    row = RuntimeSettings(id=1, admin_password_hash="")
    assert verify_admin_password("anything", row) is False
