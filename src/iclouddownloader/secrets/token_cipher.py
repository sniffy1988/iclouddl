from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from iclouddownloader.config import get_settings

_PREFIX = "fernet$"


class TokenEncryptionNotConfigured(Exception):
    """TOKEN_ENCRYPTION_KEY is missing or invalid."""


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key.strip()
    if not key:
        raise TokenEncryptionNotConfigured(
            "TOKEN_ENCRYPTION_KEY is not set. Generate with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as e:
        raise TokenEncryptionNotConfigured("TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from e


def encrypt_refresh_token(plaintext: str) -> str:
    if not plaintext:
        raise ValueError("Cannot encrypt empty refresh token")
    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def decrypt_refresh_token(ciphertext: str) -> str:
    if not ciphertext:
        raise ValueError("Cannot decrypt empty ciphertext")
    if not ciphertext.startswith(_PREFIX):
        raise ValueError("Unknown token encryption format")
    raw = ciphertext[len(_PREFIX) :]
    try:
        return _fernet().decrypt(raw.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("Refresh token decryption failed (wrong key or tampered data)") from e
