from unittest.mock import MagicMock, patch

from iclouddownloader.telegram.notifier import TelegramNotifier


def _settings(*, enabled: bool = False, token: str = ""):
    return MagicMock(
        **{
            "telegram_enabled": enabled,
            "telegram_bot_token": token,
        }
    )


@patch("iclouddownloader.telegram.notifier.get_effective_settings", return_value=_settings())
def test_notifier_daemon_alerts_disabled(_mock):
    notifier = TelegramNotifier()
    assert notifier.enabled is False
    user = type("U", (), {"apple_id": "a@b.com", "id": 1})()
    notifier.sync_started(user)


@patch(
    "iclouddownloader.telegram.notifier.get_effective_settings",
    return_value=_settings(token="123:TOKEN"),
)
@patch("iclouddownloader.telegram.notifier.httpx.AsyncClient")
def test_test_bot_token_getme(mock_client_cls, _mock_settings):
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_client_cls.return_value.__aenter__.return_value.get = MagicMock(
        return_value=mock_resp
    )

    import asyncio

    notifier = TelegramNotifier()
    ok = asyncio.run(notifier.test_bot_token())
    assert ok is True
