from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from pyicloud.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudTrustedDeviceVerificationException,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import (
    AuthChallenge,
    AuthChallengeStatus,
    AuthChallengeType,
    User,
)
from iclouddownloader.events import SyncEvent, get_event_bus
from iclouddownloader.icloud.auth import AuthRequired, get_pyicloud_service, submit_2fa_code, submit_2sa_code
from iclouddownloader.config import get_settings
from iclouddownloader.icloud.client import cookie_dir_for_user

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


_LEGACY_ACTIVITY_STATUSES = frozenset({"auth_required", "authenticated"})


class AuthService:
    CHALLENGE_TTL_MINUTES = 5

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def auth_status_for_user(user: User) -> str:
        """UI auth status: not_authorized | authorized | reauth_required | expired."""
        if not user.icloud_authenticated_at:
            return "not_authorized"
        if user.icloud_2fa_at and AuthService.days_until_2fa_expires(user) == 0:
            return "expired"
        if user.icloud_needs_auth or not AuthService.is_authorized(user):
            return "reauth_required"
        return "authorized"

    @staticmethod
    def activity_status_for_user(user: User) -> str:
        """UI sync/index status — separate from auth (never auth_required here)."""
        raw = user.last_sync_status
        if not raw or raw in _LEGACY_ACTIVITY_STATUSES:
            return "idle"
        return raw

    @staticmethod
    def _trust_anchor(user: User) -> datetime | None:
        if user.icloud_2fa_at:
            return _as_utc(user.icloud_2fa_at)
        if user.icloud_authenticated_at:
            return _as_utc(user.icloud_authenticated_at)
        return None

    @staticmethod
    def icloud_2fa_expires_at(user: User) -> datetime | None:
        anchor = AuthService._trust_anchor(user)
        if not anchor:
            return None
        days = get_settings().icloud_trusted_session_days
        return anchor + timedelta(days=days)

    @staticmethod
    def days_until_2fa_expires(user: User) -> int | None:
        """Days remaining on Apple's trusted session (default 30 days after 2FA)."""
        expires = AuthService.icloud_2fa_expires_at(user)
        if not expires:
            return None
        remaining = (expires - _utc_now()).days
        return max(remaining, 0)

    @staticmethod
    def is_authorized(user: User) -> bool:
        if user.icloud_needs_auth or not user.icloud_authenticated_at:
            return False
        expires = AuthService.icloud_2fa_expires_at(user)
        if expires and _utc_now() >= expires:
            return False
        return True

    def mark_fully_authenticated(self, user: User, *, from_2fa: bool = False) -> None:
        now = _utc_now()
        user.icloud_authenticated_at = now
        user.icloud_session_ok_at = now
        user.icloud_needs_auth = False
        if from_2fa:
            user.icloud_2fa_at = now

    def mark_session_valid(self, user: User) -> None:
        now = _utc_now()
        user.icloud_session_ok_at = now
        user.icloud_needs_auth = False
        if not user.icloud_authenticated_at:
            user.icloud_authenticated_at = now

    def mark_needs_auth(self, user: User) -> None:
        """Session expired; keep icloud_2fa_at for history."""
        user.icloud_needs_auth = True

    def handle_background_auth_required(self, user: User) -> None:
        """Scheduled sync/count failed auth — do not create new 2FA challenges."""
        self.mark_needs_auth(user)
        self.db.commit()

    def create_challenge(
        self,
        user: User,
        challenge_type: AuthChallengeType,
        prompt_message_id: str | None = None,
    ) -> AuthChallenge:
        challenge = AuthChallenge(
            user_id=user.id,
            challenge_type=challenge_type,
            status=AuthChallengeStatus.pending,
            prompt_message_id=prompt_message_id,
            expires_at=_utc_now() + timedelta(minutes=self.CHALLENGE_TTL_MINUTES),
        )
        self.db.add(challenge)
        self.db.commit()
        self.db.refresh(challenge)
        get_event_bus().publish(
            SyncEvent(
                type="auth.challenge_created",
                user_id=user.id,
                apple_id=user.apple_id,
                payload={"challenge_id": challenge.id},
            )
        )
        return challenge

    def start_authentication(self, user_id: int, password: str) -> dict:
        user = self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        cookie_dir = cookie_dir_for_user(user.id)

        # Avoid a second login (and second code) if step 2 is still pending
        existing = self.get_pending_challenge(user_id)
        if existing:
            try:
                get_pyicloud_service(user, cookie_directory=cookie_dir)
            except AuthRequired as exc:
                if exc.api is not None:
                    self.mark_needs_auth(user)
                    self.db.commit()
                    return {
                        "ok": True,
                        "status": "auth_required",
                        "challenge_type": existing.challenge_type.value,
                        "challenge_id": existing.id,
                        "message": (
                            "Use the code already sent to your device — "
                            "sign-in was not repeated"
                        ),
                    }
            else:
                self.mark_fully_authenticated(user)
                self._complete_pending_challenges(user_id)
                self.db.commit()
                return {
                    "ok": True,
                    "status": "authenticated",
                    "message": "Signed in to iCloud",
                }

        try:
            get_pyicloud_service(user, password=password, cookie_directory=cookie_dir)
        except AuthRequired as exc:
            if exc.api is None:
                raise ValueError("Invalid Apple ID or password") from exc

            challenge = self.get_pending_challenge(user_id)
            if not challenge:
                if exc.challenge_type == AuthChallengeType.twosa:
                    devices = exc.api.trusted_devices
                    if devices:
                        exc.api.send_verification_code(devices[0])
                challenge = self.create_challenge(user, exc.challenge_type)

            self.mark_needs_auth(user)
            self.db.commit()
            delivery = getattr(exc.api, "two_factor_delivery_notice", None) or (
                "Check the notification on your Mac, iPhone, or iPad "
                "(one code — use either popup or SMS if you already received both)"
            )
            return {
                "ok": True,
                "status": "auth_required",
                "challenge_type": challenge.challenge_type.value,
                "challenge_id": challenge.id,
                "message": delivery,
            }

        self.mark_fully_authenticated(user)
        self._complete_pending_challenges(user_id)
        self.db.commit()
        return {
            "ok": True,
            "status": "authenticated",
            "message": "Signed in to iCloud",
        }

    def _resolve_api_for_verification(
        self, user: User, password: str | None, cookie_dir
    ) -> tuple[object | None, bool]:
        """Return (api, fully_authenticated). Prefer cookie session from step-1 login."""
        try:
            api = get_pyicloud_service(user, cookie_directory=cookie_dir)
            return api, True
        except AuthRequired as exc:
            if exc.api is not None:
                return exc.api, False
            if not password:
                return None, False
            try:
                get_pyicloud_service(user, password=password, cookie_directory=cookie_dir)
            except AuthRequired as exc2:
                if exc2.api is None:
                    raise ValueError("Invalid Apple ID or password") from exc2
                return exc2.api, False
            api = get_pyicloud_service(user, cookie_directory=cookie_dir)
            return api, True

    def _verify_challenge_code(
        self, api, challenge_type: AuthChallengeType, code: str
    ) -> bool:
        try:
            if challenge_type == AuthChallengeType.twofa:
                return submit_2fa_code(api, code)
            return submit_2sa_code(api, 0, code)
        except PyiCloudTrustedDeviceVerificationException as e:
            raise ValueError(str(e) or "Verification failed") from e
        except PyiCloudAPIResponseException as e:
            raise ValueError(str(e) or "Verification failed") from e
        except Exception as e:
            logger.exception("Unexpected error during 2FA for user")
            raise ValueError(f"Verification failed: {e}") from e

    def _complete_pending_challenges(self, user_id: int) -> None:
        now = _utc_now()
        for challenge in self.db.scalars(
            select(AuthChallenge).where(
                AuthChallenge.user_id == user_id,
                AuthChallenge.status == AuthChallengeStatus.pending,
            )
        ).all():
            challenge.status = AuthChallengeStatus.completed
            challenge.resolved_at = now

    def get_pending_challenge(self, user_id: int) -> AuthChallenge | None:
        now = _utc_now()
        challenges = self.db.scalars(
            select(AuthChallenge)
            .where(
                AuthChallenge.user_id == user_id,
                AuthChallenge.status == AuthChallengeStatus.pending,
            )
            .order_by(AuthChallenge.created_at.desc())
        ).all()
        for challenge in challenges:
            if _as_utc(challenge.expires_at) > now:
                return challenge
        return None

    def submit_challenge_code(
        self,
        user_id: int,
        code: str,
        challenge_id: int | None = None,
        password: str | None = None,
    ) -> AuthChallenge:
        user = self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        code = code.strip()
        if not code:
            raise ValueError("Verification code is required")

        if challenge_id:
            challenge = self.db.get(AuthChallenge, challenge_id)
        else:
            challenge = self.get_pending_challenge(user_id)

        if not challenge or challenge.status != AuthChallengeStatus.pending:
            raise ValueError("No pending auth challenge")
        if _as_utc(challenge.expires_at) < _utc_now():
            challenge.status = AuthChallengeStatus.expired
            self.db.commit()
            raise ValueError("Auth challenge expired — sign in with password again")

        cookie_dir = cookie_dir_for_user(user.id)
        api, fully_authenticated = self._resolve_api_for_verification(user, password, cookie_dir)

        if not fully_authenticated:
            if api is None:
                raise ValueError(
                    "No active iCloud session — go back to step 1 and sign in with your password"
                )
            ok = self._verify_challenge_code(api, challenge.challenge_type, code)
            if not ok:
                challenge.status = AuthChallengeStatus.failed
                challenge.submitted_code = code
                self.db.commit()
                raise ValueError("Invalid verification code")

        challenge.status = AuthChallengeStatus.completed
        challenge.submitted_code = code
        challenge.resolved_at = _utc_now()
        self.mark_fully_authenticated(user, from_2fa=True)
        self.db.commit()
        self.db.refresh(challenge)
        return challenge

    def expire_stale_challenges(self) -> int:
        now = datetime.now(timezone.utc)
        challenges = list(
            self.db.scalars(
                select(AuthChallenge).where(
                    AuthChallenge.status == AuthChallengeStatus.pending,
                    AuthChallenge.expires_at <= now,
                )
            ).all()
        )
        for c in challenges:
            c.status = AuthChallengeStatus.expired
        self.db.commit()
        return len(challenges)
