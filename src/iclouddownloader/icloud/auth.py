from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pyicloud import PyiCloudService
from pyicloud.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudFailedLoginException,
    PyiCloudTrustedDeviceVerificationException,
)

from iclouddownloader.db.models import AuthChallengeType, User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_PATCHED_2FA_MODE: str | None = None


def _patch_pyicloud_2fa_delivery() -> None:
    """pyicloud default requests BOTH trusted-device push and SMS; we prefer one channel."""
    global _PATCHED_2FA_MODE
    from iclouddownloader.config import get_settings

    mode = get_settings().icloud_2fa_delivery.strip().lower()
    if _PATCHED_2FA_MODE == mode:
        return

    original = PyiCloudService._request_2fa_code

    def _request_2fa_code(self: PyiCloudService) -> None:
        headers = self._get_auth_headers({"Accept": "application/json"})
        if mode == "both":
            original(self)
            return
        if mode == "sms":
            phone = self._trusted_phone_number()
            if phone is None:
                logger.warning("SMS 2FA requested but no trusted phone number on account")
                return
            self.session.put(
                f"{self._auth_endpoint}/verify/phone",
                json={
                    "phoneNumber": phone.as_phone_number_payload(),
                    "mode": "sms",
                },
                headers=headers,
            )
            self._set_two_factor_delivery_state(
                "sms",
                "A verification code was sent by SMS.",
            )
            return
        # trusted_device (default): popup on Mac/iPhone/iPad only
        try:
            self.session.get(
                f"{self._auth_endpoint}/verify/trusteddevice",
                headers=headers,
            )
            self._set_two_factor_delivery_state(
                "trusted_device",
                "Check the notification on your Mac, iPhone, or iPad.",
            )
            logger.debug("Requested 2FA via trusted device only")
        except Exception:
            logger.debug("Trusted-device 2FA push failed", exc_info=True)

    PyiCloudService._request_2fa_code = _request_2fa_code  # type: ignore[method-assign]
    _PATCHED_2FA_MODE = mode


_patch_pyicloud_2fa_delivery()


class AuthRequired(Exception):
    def __init__(self, challenge_type: AuthChallengeType, api: PyiCloudService):
        self.challenge_type = challenge_type
        self.api = api
        super().__init__(f"Authentication required: {challenge_type.value}")


def get_pyicloud_service(
    user: User,
    password: str | None = None,
    cookie_directory: Path | None = None,
) -> PyiCloudService:
    _patch_pyicloud_2fa_delivery()
    cookie_directory = cookie_directory or Path(f"/tmp/icloud-cookies-{user.id}")
    cookie_directory.mkdir(parents=True, exist_ok=True)

    try:
        if password:
            api = PyiCloudService(user.apple_id, password, cookie_directory=str(cookie_directory))
        else:
            api = PyiCloudService(user.apple_id, cookie_directory=str(cookie_directory))
    except PyiCloudFailedLoginException as e:
        raise AuthRequired(AuthChallengeType.twofa, None) from e  # type: ignore[arg-type]

    if api.requires_2fa:
        raise AuthRequired(AuthChallengeType.twofa, api)
    if api.requires_2sa:
        raise AuthRequired(AuthChallengeType.twosa, api)

    return api


def submit_2fa_code(api: PyiCloudService, code: str) -> bool:
    try:
        result = api.validate_2fa_code(code.strip())
    except PyiCloudTrustedDeviceVerificationException:
        raise
    except PyiCloudAPIResponseException:
        return False
    if result and not api.is_trusted_session:
        try:
            api.trust_session()
        except (PyiCloudAPIResponseException, PyiCloudTrustedDeviceVerificationException):
            logger.warning("trust_session failed after 2FA", exc_info=True)
    return bool(result)


def submit_2sa_code(api: PyiCloudService, device_index: int, code: str) -> bool:
    devices = api.trusted_devices
    if device_index < 0 or device_index >= len(devices):
        return False
    device = devices[device_index]
    if not api.send_verification_code(device):
        return False
    return bool(api.validate_verification_code(device, code))


def interactive_login(user: User, password: str, cookie_dir: Path) -> PyiCloudService:
    api = PyiCloudService(user.apple_id, password, cookie_directory=str(cookie_dir))

    if api.requires_2fa:
        code = input("Enter 2FA code from your Apple device: ").strip()
        if not submit_2fa_code(api, code):
            raise RuntimeError("2FA validation failed")
    elif api.requires_2sa:
        devices = api.trusted_devices
        for i, device in enumerate(devices):
            name = device.get("deviceName", device.get("phoneNumber", "Unknown"))
            print(f"  {i}: {name}")
        idx = int(input("Select device index: ").strip() or "0")
        if not api.send_verification_code(devices[idx]):
            raise RuntimeError("Failed to send verification code")
        code = input("Enter verification code: ").strip()
        if not api.validate_verification_code(devices[idx], code):
            raise RuntimeError("2SA validation failed")
        if not api.is_trusted_session:
            api.trust_session()

    return api
