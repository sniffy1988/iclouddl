from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from iclouddownloader.services.runtime_settings_service import get_effective_settings
from iclouddownloader.db.models import AuthChallenge, AuthChallengeStatus
from iclouddownloader.services.auth_service import AuthService

logger = logging.getLogger(__name__)

CODE_PATTERN = re.compile(r"^/code\s+(\d{4,8})$", re.IGNORECASE)


class TwoFAHandler:
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.settings = get_effective_settings()

    def is_allowed_chat(self, chat_id: int, user_id: int | None = None) -> bool:
        admin = self.settings.telegram_admin_chat_id
        if str(chat_id) != str(admin):
            return False
        allowed = self.settings.telegram_allowed_ids
        if allowed and user_id is not None and user_id not in allowed:
            return False
        return True

    def handle_message(self, chat_id: int, text: str, from_user_id: int | None = None) -> str | None:
        if not self.is_allowed_chat(chat_id, from_user_id):
            return None

        match = CODE_PATTERN.match(text.strip())
        if not match:
            return None

        code = match.group(1)
        from sqlalchemy import select

        challenge = self.db.scalar(
            select(AuthChallenge)
            .where(AuthChallenge.status == AuthChallengeStatus.pending)
            .order_by(AuthChallenge.created_at.desc())
        )

        if not challenge:
            return "No pending 2FA challenge."

        try:
            self.auth_service.submit_challenge_code(challenge.user_id, code, challenge.id)
            return f"Code accepted for user {challenge.user_id}. Session updated."
        except ValueError as e:
            return f"Failed: {e}"
