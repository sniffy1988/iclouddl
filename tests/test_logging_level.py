import logging

from iclouddownloader.logging_setup import (
    LOG_LEVEL_NAMES,
    ColoredConsoleFormatter,
    console_use_color,
    normalize_log_level,
    should_log_http_requests,
)


def test_normalize_log_level():
    assert normalize_log_level("info") == "INFO"
    assert normalize_log_level("OFF") == "OFF"
    assert normalize_log_level("bogus") == "OFF"


def test_should_log_http_requests_off_by_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    from iclouddownloader.config import get_settings

    get_settings.cache_clear()
    assert should_log_http_requests() is False


def test_log_level_names_complete():
    assert "DEBUG" in LOG_LEVEL_NAMES
    assert "OFF" in LOG_LEVEL_NAMES


def test_console_use_color_respects_no_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("ICLD_LOG_COLOR", "1")
    assert console_use_color() in (True, False)
    monkeypatch.setenv("NO_COLOR", "1")
    assert console_use_color() is False


def test_colored_formatter_plain_has_no_ansi():
    fmt = ColoredConsoleFormatter(use_color=False)
    record = logging.LogRecord(
        name="iclouddownloader.test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    out = fmt.format(record)
    assert "\033[" not in out
    assert "INFO" in out
    assert "hello" in out


def test_colored_formatter_color_includes_ansi():
    fmt = ColoredConsoleFormatter(use_color=True)
    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="boom",
        args=(),
        exc_info=None,
    )
    out = fmt.format(record)
    assert "\033[" in out
    assert "ERROR" in out
    assert "boom" in out
