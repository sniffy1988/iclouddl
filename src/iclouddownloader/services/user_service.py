from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.config import get_settings
from iclouddownloader.db.models import User
from iclouddownloader.icloud.client import download_dir_for_user
from iclouddownloader.providers.base import linked_providers


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.id)).all())

    def get_user(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_apple_id(self, apple_id: str) -> User | None:
        return self.db.scalar(select(User).where(User.apple_id == apple_id))

    @staticmethod
    def validate_has_provider(user: User) -> None:
        if not linked_providers(user) and not user.apple_id and not user.google_account_email:
            raise ValueError("Link at least iCloud (Apple ID) or Google Photos before syncing")

    def create_user(
        self,
        apple_id: str | None = None,
        display_name: str | None = None,
        download_dir: str | None = None,
        sync_interval_seconds: int | None = None,
        library_key: str = "root",
    ) -> User:
        settings = get_settings()
        interval = sync_interval_seconds or settings.default_sync_interval_seconds
        label = display_name or apple_id or "New user"
        user = User(
            apple_id=apple_id,
            display_name=label,
            download_dir=download_dir or "",
            sync_interval_seconds=interval,
            library_key=library_key,
            next_sync_at=datetime.now(timezone.utc),
            icloud_needs_auth=bool(apple_id),
        )
        self.db.add(user)
        self.db.flush()
        if not user.download_dir:
            user.download_dir = str(
                download_dir_for_user(user.id, apple_id or f"user-{user.id}", custom_dir=None)
            )
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(self, user_id: int, **kwargs) -> User:
        user = self.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        reschedule = bool(kwargs.pop("reschedule_sync", False))
        interval_changed = False
        was_enabled = user.enabled

        for key, value in list(kwargs.items()):
            if not hasattr(user, key):
                continue
            if value is None:
                continue
            if key == "sync_interval_seconds":
                interval_changed = True
            if key == "immich_library_id":
                user.immich_library_id = str(value).strip() or None
                continue
            if key == "apple_id" and value:
                user.apple_id = str(value).strip()
                continue
            setattr(user, key, value)

        if user.enabled and not was_enabled and user.next_sync_at is None:
            user.next_sync_at = datetime.now(timezone.utc)

        if user.enabled and (reschedule or interval_changed):
            user.next_sync_at = datetime.now(timezone.utc) + timedelta(
                seconds=user.sync_interval_seconds
            )

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> None:
        user = self.get_user(user_id)
        if user:
            self.db.delete(user)
            self.db.commit()

    def set_enabled(self, user_id: int, enabled: bool) -> User:
        return self.update_user(user_id, enabled=enabled)

    def schedule_next_sync(self, user: User) -> None:
        user.next_sync_at = datetime.now(timezone.utc) + timedelta(seconds=user.sync_interval_seconds)
        self.db.commit()

    def users_due_for_sync(self) -> list[User]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(User)
            .where(User.enabled.is_(True))
            .where((User.next_sync_at.is_(None)) | (User.next_sync_at <= now))
        )
        return list(self.db.scalars(stmt).all())
