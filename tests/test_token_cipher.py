import os

import pytest
from cryptography.fernet import Fernet

from iclouddownloader.config import get_settings
from iclouddownloader.secrets.token_cipher import (
    TokenEncryptionNotConfigured,
    decrypt_refresh_token,
    encrypt_refresh_token,
)


@pytest.fixture(autouse=True)
def fernet_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_encrypt_decrypt_roundtrip():
    plain = "refresh-token-secret"
    enc = encrypt_refresh_token(plain)
    assert enc.startswith("fernet$")
    assert enc != plain
    assert decrypt_refresh_token(enc) == plain


def test_wrong_key_fails(monkeypatch):
    enc = encrypt_refresh_token("token-a")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="decryption failed"):
        decrypt_refresh_token(enc)


def test_missing_key():
    os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
    get_settings.cache_clear()
    with pytest.raises(TokenEncryptionNotConfigured):
        encrypt_refresh_token("x")
