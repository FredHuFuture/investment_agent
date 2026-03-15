"""Tests for Sprint 12.1: Email notification dispatcher.

Covers EmailConfig, EmailDispatcher, HTML email building, and SMTP mocking.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from notifications.email_dispatcher import EmailConfig, EmailDispatcher


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _sample_alert(
    ticker: str = "AAPL",
    alert_type: str = "STOP_LOSS_HIT",
    severity: str = "CRITICAL",
    message: str = "Price dropped below stop-loss at $145.00",
    recommended_action: str = "Review position and consider closing",
    current_price: float = 142.50,
) -> dict:
    return {
        "ticker": ticker,
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "recommended_action": recommended_action,
        "current_price": current_price,
        "created_at": "2026-03-14 10:00 UTC",
    }


def _make_config(**overrides) -> EmailConfig:
    defaults = {
        "smtp_host": "smtp.test.local",
        "smtp_port": 587,
        "smtp_user": "user@test.local",
        "smtp_password": "secret",
        "from_address": "alerts@test.local",
        "to_addresses": ["admin@test.local"],
        "use_tls": True,
    }
    defaults.update(overrides)
    return EmailConfig(**defaults)


# ---------------------------------------------------------------------------
# 1. test_email_config_from_env
# ---------------------------------------------------------------------------

def test_email_config_from_env():
    """Set env vars, verify EmailConfig parses correctly."""
    env = {
        "SMTP_HOST": "mail.example.com",
        "SMTP_PORT": "465",
        "SMTP_USER": "bot@example.com",
        "SMTP_PASSWORD": "p@ss",
        "ALERT_FROM_EMAIL": "noreply@example.com",
        "ALERT_TO_EMAILS": "alice@x.com, bob@x.com",
        "SMTP_USE_TLS": "false",
    }
    with patch.dict(os.environ, env, clear=False):
        cfg = EmailConfig.from_env()

    assert cfg is not None
    assert cfg.smtp_host == "mail.example.com"
    assert cfg.smtp_port == 465
    assert cfg.smtp_user == "bot@example.com"
    assert cfg.smtp_password == "p@ss"
    assert cfg.from_address == "noreply@example.com"
    assert cfg.to_addresses == ["alice@x.com", "bob@x.com"]
    assert cfg.use_tls is False


# ---------------------------------------------------------------------------
# 2. test_email_config_missing
# ---------------------------------------------------------------------------

def test_email_config_missing():
    """No SMTP_HOST env var => returns None."""
    env_clear = {
        "SMTP_HOST": "",
    }
    with patch.dict(os.environ, env_clear, clear=False):
        # Remove SMTP_HOST if it exists
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SMTP_HOST", None)
            cfg = EmailConfig.from_env()
    assert cfg is None


# ---------------------------------------------------------------------------
# 3. test_dispatcher_not_configured
# ---------------------------------------------------------------------------

async def test_dispatcher_not_configured():
    """No config => is_configured=False, send returns False."""
    dispatcher = EmailDispatcher(config=None)
    # Override _config to ensure None
    dispatcher._config = None

    assert dispatcher.is_configured is False
    result = await dispatcher.send_alert(_sample_alert())
    assert result is False

    result2 = await dispatcher.send_alert_digest([_sample_alert()])
    assert result2 is False


# ---------------------------------------------------------------------------
# 4. test_build_alert_email_subject
# ---------------------------------------------------------------------------

def test_build_alert_email_subject():
    """Verify subject format for a CRITICAL alert."""
    config = _make_config()
    dispatcher = EmailDispatcher(config=config)
    alert = _sample_alert(ticker="AAPL", alert_type="STOP_LOSS_HIT", severity="CRITICAL")

    subject, _ = dispatcher._build_alert_email(alert)

    assert "[CRITICAL]" in subject
    assert "AAPL" in subject
    assert "Stop loss hit" in subject
    assert "Investment Agent" in subject


# ---------------------------------------------------------------------------
# 5. test_build_alert_email_html
# ---------------------------------------------------------------------------

def test_build_alert_email_html():
    """Verify HTML body contains ticker, message, severity."""
    config = _make_config()
    dispatcher = EmailDispatcher(config=config)
    alert = _sample_alert(
        ticker="TSLA",
        severity="HIGH",
        message="Significant loss detected",
        recommended_action="Review position",
        current_price=210.50,
    )

    _, html = dispatcher._build_alert_email(alert)

    assert "TSLA" in html
    assert "Significant loss detected" in html
    assert "HIGH" in html
    assert "Review position" in html
    assert "$210.50" in html
    # Dark theme class present
    assert "badge-high" in html


# ---------------------------------------------------------------------------
# 6. test_build_digest_email
# ---------------------------------------------------------------------------

def test_build_digest_email():
    """Verify digest email contains multiple alert summaries."""
    config = _make_config()
    dispatcher = EmailDispatcher(config=config)
    alerts = [
        _sample_alert(ticker="AAPL", severity="CRITICAL", message="Stop loss hit"),
        _sample_alert(ticker="MSFT", severity="HIGH", message="Signal reversal"),
        _sample_alert(ticker="GOOG", severity="HIGH", message="Significant loss"),
    ]

    subject, html = dispatcher._build_digest_email(alerts)

    # Subject should mention count
    assert "3 new alerts" in subject
    assert "Alert Digest" in subject
    assert "Investment Agent" in subject

    # HTML should include all tickers
    assert "AAPL" in html
    assert "MSFT" in html
    assert "GOOG" in html

    # Each alert message present
    assert "Stop loss hit" in html
    assert "Signal reversal" in html
    assert "Significant loss" in html


# ---------------------------------------------------------------------------
# 7. test_send_alert_mock_smtp
# ---------------------------------------------------------------------------

async def test_send_alert_mock_smtp():
    """Mock smtplib.SMTP, verify send_message is called."""
    config = _make_config()
    dispatcher = EmailDispatcher(config=config)
    alert = _sample_alert()

    mock_smtp_instance = MagicMock()
    mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
    # Make it work as context manager
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)

    with patch("notifications.email_dispatcher.smtplib.SMTP", mock_smtp_class):
        result = await dispatcher.send_alert(alert)

    assert result is True
    # SMTP was instantiated with correct host/port
    mock_smtp_class.assert_called_once_with(config.smtp_host, config.smtp_port)
    # TLS + login + send_message were called
    mock_smtp_instance.ehlo.assert_called()
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with(config.smtp_user, config.smtp_password)
    mock_smtp_instance.send_message.assert_called_once()

    # Verify the message passed to send_message
    sent_msg = mock_smtp_instance.send_message.call_args[0][0]
    assert "[CRITICAL]" in sent_msg["Subject"]
    assert "AAPL" in sent_msg["Subject"]


# ---------------------------------------------------------------------------
# 8. test_send_alert_smtp_error
# ---------------------------------------------------------------------------

async def test_send_alert_smtp_error():
    """Mock SMTP raising exception => returns False, no crash."""
    config = _make_config()
    dispatcher = EmailDispatcher(config=config)
    alert = _sample_alert()

    mock_smtp_instance = MagicMock()
    mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)
    mock_smtp_instance.send_message.side_effect = ConnectionRefusedError("Connection refused")

    with patch("notifications.email_dispatcher.smtplib.SMTP", mock_smtp_class):
        result = await dispatcher.send_alert(alert)

    assert result is False


# ---------------------------------------------------------------------------
# Extra: test dispatcher with empty to_addresses
# ---------------------------------------------------------------------------

async def test_dispatcher_no_recipients():
    """Config with empty to_addresses => is_configured=False."""
    config = _make_config(to_addresses=[])
    dispatcher = EmailDispatcher(config=config)
    assert dispatcher.is_configured is False

    result = await dispatcher.send_alert(_sample_alert())
    assert result is False


# ---------------------------------------------------------------------------
# Extra: test digest with single alert (no plural "s")
# ---------------------------------------------------------------------------

def test_build_digest_single_alert():
    """Single-alert digest uses singular form in subject."""
    config = _make_config()
    dispatcher = EmailDispatcher(config=config)
    alerts = [_sample_alert(ticker="NVDA")]

    subject, _ = dispatcher._build_digest_email(alerts)
    assert "1 new alert" in subject
    # Should NOT say "1 new alerts"
    assert "1 new alerts" not in subject


# ---------------------------------------------------------------------------
# Extra: test send_alert_digest with empty list
# ---------------------------------------------------------------------------

async def test_send_digest_empty_list():
    """Empty alert list => returns False without sending."""
    config = _make_config()
    dispatcher = EmailDispatcher(config=config)

    result = await dispatcher.send_alert_digest([])
    assert result is False
