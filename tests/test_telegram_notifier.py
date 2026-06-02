from unittest.mock import MagicMock, patch

from iclouddownloader.telegram.notifier import TelegramNotifier


def _disabled_settings():
    return MagicMock(
        **{
            "telegram_enabled": False,
            "telegram_bot_token": "",
            "telegram_admin_chat_id": "",
        }
    )


@patch("iclouddownloader.telegram.notifier.get_effective_settings", return_value=_disabled_settings())
def test_notifier_disabled_by_default(_mock):
    notifier = TelegramNotifier()
    assert notifier.enabled is False


@patch("iclouddownloader.telegram.notifier.get_effective_settings", return_value=_disabled_settings())
def test_notifier_sync_started_no_crash(_mock):
    notifier = TelegramNotifier()
    user = type("U", (), {"apple_id": "a@b.com", "id": 1})()
    notifier.sync_started(user)  # should no-op when disabled
