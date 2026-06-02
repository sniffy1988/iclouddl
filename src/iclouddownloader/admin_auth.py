"""Web admin password — stored only in runtime_settings (database)."""

from __future__ import annotations

import bcrypt
from sqlalchemy.orm import Session

from iclouddownloader.db.models import RuntimeSettings


def hash_admin_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def admin_configured(row: RuntimeSettings | None) -> bool:
    return bool(row and row.admin_password_hash)


def verify_admin_password(password: str, row: RuntimeSettings | None) -> bool:
    if not admin_configured(row):
        return False
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            row.admin_password_hash.encode("utf-8"),  # type: ignore[union-attr]
        )
    except ValueError:
        return False


def set_admin_password(db: Session, row: RuntimeSettings, password: str) -> None:
    row.admin_password_hash = hash_admin_password(password.strip())
    db.commit()
