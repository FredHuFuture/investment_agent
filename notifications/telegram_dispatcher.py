"""Telegram Bot API notification dispatcher for investment alerts."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# Severity → emoji mapping
_SEVERITY_EMOJI: dict[str, str] = {
    "CRITICAL": "\U0001f534",  # Red circle
    "HIGH": "\U0001f7e0",      # Orange circle
    "WARNING": "\U0001f7e1",   # Yellow circle
    "INFO": "\U0001f535",      # Blue circle
}


class TelegramDispatcher:
    """Send alert notifications to a Telegram chat via Bot API."""

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        self._token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self._chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    @property
    def is_configured(self) -> bool:
        """Return True if both bot token and chat ID are set."""
        return bool(self._token) and bool(self._chat_id)

    async def send_alert(self, alert: dict[str, Any]) -> bool:
        """Send a single alert as a Telegram message. Returns True if sent."""
        if not self.is_configured:
            logger.warning("Telegram not configured — skipping alert dispatch")
            return False

        text = self._format_alert_message(alert)
        return await self._send_message(text)

    async def send_alert_digest(self, alerts: list[dict[str, Any]]) -> bool:
        """Send a digest of alerts as a single Telegram message."""
        if not self.is_configured:
            logger.warning("Telegram not configured — skipping digest dispatch")
            return False

        if not alerts:
            logger.info("No alerts to send in digest")
            return False

        text = self._format_digest_message(alerts)
        return await self._send_message(text)

    def _format_alert_message(self, alert: dict[str, Any]) -> str:
        """Format a single alert as an HTML message for Telegram."""
        severity = alert.get("severity", "INFO")
        emoji = _SEVERITY_EMOJI.get(severity, _SEVERITY_EMOJI["INFO"])
        ticker = alert.get("ticker", "N/A")
        alert_type = alert.get("alert_type", "UNKNOWN")
        message = alert.get("message", "")
        action = alert.get("recommended_action", "")
        price = alert.get("current_price")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"{emoji} <b>{severity} \u2014 {ticker}</b>",
            f"<b>Type:</b> {alert_type}",
            f"<b>Message:</b> {message}",
        ]
        if action:
            lines.append(f"<b>Action:</b> {action}")
        if price is not None:
            lines.append(f"<b>Price:</b> ${price:,.2f}")
        lines.append(f"\u23f0 {timestamp}")

        return "\n".join(lines)

    def _format_digest_message(self, alerts: list[dict[str, Any]]) -> str:
        """Format a digest of alerts as an HTML message for Telegram."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        header = (
            f"\U0001f4ca <b>Alert Digest</b> \u2014 {len(alerts)} alert(s)\n"
            f"\u23f0 {timestamp}\n"
            f"\u2500" * 20
        )
        items: list[str] = []
        for i, alert in enumerate(alerts, 1):
            severity = alert.get("severity", "INFO")
            emoji = _SEVERITY_EMOJI.get(severity, _SEVERITY_EMOJI["INFO"])
            ticker = alert.get("ticker", "N/A")
            message = alert.get("message", "")
            items.append(f"{i}. {emoji} <b>{ticker}</b> \u2014 {message}")

        return header + "\n" + "\n".join(items)

    async def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message via Telegram Bot API.

        Returns True on success, False on failure (logs warning).
        """
        url = f"{self.BASE_URL.format(token=self._token)}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info("Telegram message sent successfully")
                        return True
                    body = await resp.text()
                    logger.warning(
                        "Telegram API error %d: %s", resp.status, body
                    )
                    return False
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)
            return False
