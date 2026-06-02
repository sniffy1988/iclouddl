from unittest.mock import MagicMock, patch

from iclouddownloader.integrations.immich import ImmichClient, _last_scan_at


def _settings(**kwargs):
    defaults = {
        "immich_enabled": True,
        "immich_base_url": "https://immich.test",
        "immich_api_key": "secret",
        "immich_scan_debounce_seconds": 3600,
    }
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _user(**kwargs):
    defaults = {
        "immich_library_id": "lib-uuid",
        "immich_scan_after_sync": True,
        "apple_id": "a@b.com",
    }
    defaults.update(kwargs)
    return MagicMock(**defaults)


def test_immich_configured_and_should_scan():
    client = ImmichClient()
    client.settings = _settings()
    assert client.configured is True
    assert client.should_scan_after_sync(_user()) is True
    assert client.should_scan_after_sync(_user(immich_scan_after_sync=False)) is False
    assert client.should_scan_after_sync(_user(immich_library_id=None)) is False


def test_immich_scan_debounce():
    _last_scan_at.clear()
    client = ImmichClient()
    client.settings = _settings(immich_scan_debounce_seconds=3600)

    with patch("iclouddownloader.integrations.immich.httpx.Client") as mock_client:
        mock_resp = MagicMock(status_code=204, text="")
        mock_client.return_value.__enter__.return_value.post.return_value = mock_resp

        ok1, _ = client.trigger_library_scan("lib-uuid", force=False)
        ok2, msg2 = client.trigger_library_scan("lib-uuid", force=False)

    assert ok1 is True
    assert ok2 is True
    assert "debounced" in msg2.lower()
