from __future__ import annotations

import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import AuthChallenge, AuthChallengeStatus
from iclouddownloader.services.auth_service import AuthService
from iclouddownloader.services.runtime_settings_service import get_effective_settings

logger = logging.getLogger(__name__)

CODE_PATTERN = re.compile(r"^/code\s+(\d{4,8})$", re.IGNORECASE)


class TwoFAHandler:
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)
        self.settings = get_effective_settings()

    def is_allowed_chat(self, chat_id: int, user_id: int | None = None) -> bool:
        return bool(
            self.settings.telegram_enabled and (self.settings.telegram_bot_token or "").strip()
        )

    def handle_message(self, chat_id: int, text: str, from_user_id: int | None = None) -> str | None:
        if not self.is_allowed_chat(chat_id, from_user_id):
            return None

        match = CODE_PATTERN.match(text.strip())
        if not match:
            return None

        code = match.group(1)
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
