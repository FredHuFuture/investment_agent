"""Tests for the Telegram notification dispatcher."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from notifications.telegram_dispatcher import TelegramDispatcher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def _telegram_env(monkeypatch):
    """Set Telegram env vars for tests that need a configured dispatcher."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567890")


@pytest.fixture()
def _no_telegram_env(monkeypatch):
    """Ensure Telegram env vars are NOT set."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)


@pytest.fixture()
def sample_critical_alert() -> dict:
    return {
        "ticker": "AAPL",
        "alert_type": "STOP_LOSS_HIT",
        "severity": "CRITICAL",
        "message": "AAPL dropped below stop loss at $145.00",
        "recommended_action": "Review position immediately",
        "current_price": 142.50,
    }


@pytest.fixture()
def sample_warning_alert() -> dict:
    return {
        "ticker": "MSFT",
        "alert_type": "SIGNIFICANT_LOSS",
        "severity": "WARNING",
        "message": "MSFT down 5% in the last week",
        "recommended_action": "Monitor closely",
        "current_price": 380.00,
    }


@pytest.fixture()
def sample_alerts(sample_critical_alert, sample_warning_alert) -> list[dict]:
    return [
        sample_critical_alert,
        sample_warning_alert,
        {
            "ticker": "GOOG",
            "alert_type": "TARGET_HIT",
            "severity": "INFO",
            "message": "GOOG reached target price of $180.00",
            "recommended_action": "Consider taking profits",
            "current_price": 181.25,
        },
    ]


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_telegram_env")
def test_telegram_configured():
    """With env vars set, dispatcher should report is_configured=True."""
    tg = TelegramDispatcher()
    assert tg.is_configured is True


@pytest.mark.usefixtures("_no_telegram_env")
def test_telegram_not_configured():
    """Without env vars, dispatcher should report is_configured=False."""
    tg = TelegramDispatcher()
    assert tg.is_configured is False


@pytest.mark.usefixtures("_no_telegram_env")
@pytest.mark.asyncio
async def test_send_returns_false_when_not_configured():
    """send_alert should return False and not attempt HTTP when not configured."""
    tg = TelegramDispatcher()
    result = await tg.send_alert({"severity": "INFO", "ticker": "X", "message": "test"})
    assert result is False


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_telegram_env")
def test_format_alert_critical(sample_critical_alert):
    """Critical alerts should include the red circle emoji and HTML formatting."""
    tg = TelegramDispatcher()
    text = tg._format_alert_message(sample_critical_alert)

    assert "\U0001f534" in text  # Red circle emoji
    assert "<b>CRITICAL" in text
    assert "AAPL" in text
    assert "STOP_LOSS_HIT" in text
    assert "$142.50" in text
    assert "<b>Action:</b>" in text
    assert "Review position immediately" in text


@pytest.mark.usefixtures("_telegram_env")
def test_format_alert_warning(sample_warning_alert):
    """Warning alerts should include the yellow circle emoji."""
    tg = TelegramDispatcher()
    text = tg._format_alert_message(sample_warning_alert)

    assert "\U0001f7e1" in text  # Yellow circle emoji
    assert "<b>WARNING" in text
    assert "MSFT" in text


@pytest.mark.usefixtures("_telegram_env")
def test_format_digest(sample_alerts):
    """Digest should contain header, count, and all alert tickers."""
    tg = TelegramDispatcher()
    text = tg._format_digest_message(sample_alerts)

    assert "Alert Digest" in text
    assert "3 alert(s)" in text
    assert "AAPL" in text
    assert "MSFT" in text
    assert "GOOG" in text
    # Numbered list
    assert "1." in text
    assert "2." in text
    assert "3." in text


# ---------------------------------------------------------------------------
# HTTP sending tests (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_telegram_env")
@pytest.mark.asyncio
async def test_send_message_success(sample_critical_alert):
    """Mocked 200 response from Telegram API should return True."""
    tg = TelegramDispatcher()

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("notifications.telegram_dispatcher.aiohttp.ClientSession", return_value=mock_session):
        result = await tg.send_alert(sample_critical_alert)

    assert result is True
    mock_session.post.assert_called_once()
    call_args = mock_session.post.call_args
    assert "/sendMessage" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["chat_id"] == "-1001234567890"
    assert payload["parse_mode"] == "HTML"


@pytest.mark.usefixtures("_telegram_env")
@pytest.mark.asyncio
async def test_send_message_api_error(sample_critical_alert):
    """Mocked 400 response from Telegram API should return False."""
    tg = TelegramDispatcher()

    mock_resp = AsyncMock()
    mock_resp.status = 400
    mock_resp.text = AsyncMock(return_value='{"ok":false,"description":"Bad Request"}')
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("notifications.telegram_dispatcher.aiohttp.ClientSession", return_value=mock_session):
        result = await tg.send_alert(sample_critical_alert)

    assert result is False


@pytest.mark.usefixtures("_telegram_env")
@pytest.mark.asyncio
async def test_send_message_network_error(sample_critical_alert):
    """Network exception during send should return False, not raise."""
    tg = TelegramDispatcher()

    mock_session = AsyncMock()
    mock_session.post = MagicMock(side_effect=Exception("Connection refused"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("notifications.telegram_dispatcher.aiohttp.ClientSession", return_value=mock_session):
        result = await tg.send_alert(sample_critical_alert)

    assert result is False
