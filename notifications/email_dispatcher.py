"""Email notification dispatcher for CRITICAL/HIGH investment alerts.

Uses Python's built-in smtplib and email.mime -- no external dependencies.
SMTP send runs in a thread executor to avoid blocking the async event loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """Email dispatch configuration from environment variables."""

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_address: str
    to_addresses: list[str] = field(default_factory=list)
    use_tls: bool = True

    @classmethod
    def from_env(cls) -> "EmailConfig | None":
        """Load config from env vars. Returns None if not configured."""
        host = os.getenv("SMTP_HOST")
        if not host:
            return None
        return cls(
            smtp_host=host,
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            from_address=os.getenv("ALERT_FROM_EMAIL", "alerts@investment-agent.local"),
            to_addresses=[
                a.strip()
                for a in os.getenv("ALERT_TO_EMAILS", "").split(",")
                if a.strip()
            ],
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
        )


# ---------------------------------------------------------------------------
# HTML email styling (dark theme)
# ---------------------------------------------------------------------------

_CSS = """
body {
  margin: 0; padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  background-color: #1a1a2e; color: #e0e0e0;
}
.container {
  max-width: 600px; margin: 0 auto; padding: 24px;
  background-color: #16213e; border-radius: 8px;
}
h1 { color: #e94560; font-size: 22px; margin-top: 0; }
h2 { color: #e94560; font-size: 18px; margin-top: 24px; }
.badge {
  display: inline-block; padding: 3px 10px; border-radius: 4px;
  font-size: 12px; font-weight: 700; text-transform: uppercase; color: #fff;
}
.badge-critical { background-color: #e94560; }
.badge-high     { background-color: #e67e22; }
.badge-warning  { background-color: #f1c40f; color: #222; }
.badge-info     { background-color: #3498db; }
.alert-card {
  background-color: #0f3460; border-radius: 6px; padding: 16px;
  margin-bottom: 16px; border-left: 4px solid #e94560;
}
.ticker { font-size: 20px; font-weight: 700; color: #00d2ff; }
.label  { color: #8899aa; font-size: 12px; text-transform: uppercase; margin-top: 10px; }
.value  { color: #e0e0e0; font-size: 14px; margin-top: 2px; }
.footer {
  text-align: center; font-size: 11px; color: #556677;
  margin-top: 24px; padding-top: 16px; border-top: 1px solid #1a3055;
}
"""

_SEVERITY_BADGE_CLASS = {
    "CRITICAL": "badge-critical",
    "HIGH": "badge-high",
    "WARNING": "badge-warning",
    "INFO": "badge-info",
}


def _severity_badge(severity: str) -> str:
    css_class = _SEVERITY_BADGE_CLASS.get(severity.upper(), "badge-info")
    return f'<span class="badge {css_class}">{severity.upper()}</span>'


def _timestamp_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# EmailDispatcher
# ---------------------------------------------------------------------------


class EmailDispatcher:
    """Dispatch alert emails via SMTP.

    If SMTP is not configured (no env vars), all send methods return False
    with a log warning -- they never crash.
    """

    def __init__(self, config: EmailConfig | None = None) -> None:
        self._config = config or EmailConfig.from_env()

    @property
    def is_configured(self) -> bool:
        """True when we have a config with at least one recipient."""
        return self._config is not None and len(self._config.to_addresses) > 0

    # -- public async API ---------------------------------------------------

    async def send_alert(self, alert: dict[str, Any]) -> bool:
        """Send a single alert email. Returns True if sent successfully."""
        if not self.is_configured:
            logger.warning("Email not configured -- skipping alert email")
            return False

        subject, html_body = self._build_alert_email(alert)
        return await self._send_async(subject, html_body)

    async def send_alert_digest(self, alerts: list[dict[str, Any]]) -> bool:
        """Send a digest of multiple alerts in one email."""
        if not self.is_configured:
            logger.warning("Email not configured -- skipping alert digest email")
            return False

        if not alerts:
            return False

        subject, html_body = self._build_digest_email(alerts)
        return await self._send_async(subject, html_body)

    # -- email builders -----------------------------------------------------

    def _build_alert_email(self, alert: dict[str, Any]) -> tuple[str, str]:
        """Build (subject, html_body) for a single alert."""
        severity = alert.get("severity", "INFO").upper()
        ticker = alert.get("ticker", "???")
        alert_type = alert.get("alert_type", "ALERT")
        message = alert.get("message", "")
        recommended_action = alert.get("recommended_action", "")
        current_price = alert.get("current_price")
        timestamp = alert.get("created_at", _timestamp_str())

        # Subject: [CRITICAL] AAPL: Stop loss hit -- Investment Agent
        subject = f"[{severity}] {ticker}: {_type_label(alert_type)} \u2014 Investment Agent"

        price_html = ""
        if current_price is not None:
            price_html = f"""
            <div class="label">Current Price</div>
            <div class="value">${current_price:,.2f}</div>
            """

        html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_CSS}</style></head>
<body><div class="container">
  <h1>Investment Agent Alert</h1>
  <div class="alert-card">
    <div><span class="ticker">{ticker}</span> {_severity_badge(severity)}</div>
    <div class="label">Alert Type</div>
    <div class="value">{_type_label(alert_type)}</div>
    <div class="label">Message</div>
    <div class="value">{message}</div>
    {price_html}
    <div class="label">Recommended Action</div>
    <div class="value">{recommended_action}</div>
    <div class="label">Timestamp</div>
    <div class="value">{timestamp}</div>
  </div>
  <div class="footer">Investment Agent &mdash; Automated Alert System</div>
</div></body></html>"""

        return subject, html_body

    def _build_digest_email(self, alerts: list[dict[str, Any]]) -> tuple[str, str]:
        """Build (subject, html_body) for alert digest."""
        count = len(alerts)
        subject = f"[Alert Digest] {count} new alert{'s' if count != 1 else ''} \u2014 Investment Agent"

        cards_html = ""
        for alert in alerts:
            severity = alert.get("severity", "INFO").upper()
            ticker = alert.get("ticker", "???")
            alert_type = alert.get("alert_type", "ALERT")
            message = alert.get("message", "")
            recommended_action = alert.get("recommended_action", "")
            current_price = alert.get("current_price")

            price_html = ""
            if current_price is not None:
                price_html = f"""
                <div class="label">Current Price</div>
                <div class="value">${current_price:,.2f}</div>
                """

            cards_html += f"""
            <div class="alert-card">
              <div><span class="ticker">{ticker}</span> {_severity_badge(severity)}</div>
              <div class="label">Alert Type</div>
              <div class="value">{_type_label(alert_type)}</div>
              <div class="label">Message</div>
              <div class="value">{message}</div>
              {price_html}
              <div class="label">Recommended Action</div>
              <div class="value">{recommended_action}</div>
            </div>
            """

        html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_CSS}</style></head>
<body><div class="container">
  <h1>Alert Digest &mdash; {count} Alert{'s' if count != 1 else ''}</h1>
  <p style="color:#8899aa;font-size:13px;">Generated at {_timestamp_str()}</p>
  {cards_html}
  <div class="footer">Investment Agent &mdash; Automated Alert System</div>
</div></body></html>"""

        return subject, html_body

    async def send_markdown_email(
        self, subject: str, markdown_body: str
    ) -> bool:
        """Send a Markdown body wrapped in <pre> inside the HTML template.

        LIVE-04 (Phase 7): the weekly digest body is machine-generated by
        engine.digest.render_weekly_digest — no user-supplied text — so
        <pre>-wrap with html.escape() is sufficient (T-07-02-01 mitigation).

        Returns False (not crash) when is_configured is False.
        """
        if not self.is_configured:
            logger.warning(
                "Email not configured -- skipping markdown digest email"
            )
            return False

        import html as _html  # stdlib, lazy import

        escaped = _html.escape(markdown_body)
        html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{_CSS}
pre {{ font-family: ui-monospace, SFMono-Regular, monospace;
        white-space: pre-wrap; color: #e0e0e0;
        background: #0f3460; padding: 16px; border-radius: 6px;
        font-size: 13px; line-height: 1.5; }}
</style></head>
<body><div class="container">
  <h1>Investment Agent &#x2014; Weekly Digest</h1>
  <pre>{escaped}</pre>
  <div class="footer">Investment Agent &mdash; Weekly Digest</div>
</div></body></html>"""

        return await self._send_async(subject, html_body)

    # -- SMTP transport (sync, run in executor) -----------------------------

    async def _send_async(self, subject: str, html_body: str) -> bool:
        """Run the blocking SMTP send in a thread executor."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._send_sync, subject, html_body)
            return True
        except Exception as exc:
            logger.error("Failed to send email: %s", exc, exc_info=True)
            return False

    def _send_sync(self, subject: str, html_body: str) -> None:
        """Blocking SMTP send. Called from executor thread."""
        assert self._config is not None  # guarded by is_configured check

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._config.from_address
        msg["To"] = ", ".join(self._config.to_addresses)

        # Attach HTML body
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if self._config.use_tls:
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if self._config.smtp_user:
                    server.login(self._config.smtp_user, self._config.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port) as server:
                if self._config.smtp_user:
                    server.login(self._config.smtp_user, self._config.smtp_password)
                server.send_message(msg)

        logger.info("Email sent: %s -> %s", subject, self._config.to_addresses)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALERT_TYPE_LABELS = {
    "STOP_LOSS_HIT": "Stop loss hit",
    "TARGET_HIT": "Target hit",
    "TIME_OVERRUN": "Time overrun",
    "SIGNIFICANT_LOSS": "Significant loss",
    "SIGNIFICANT_GAIN": "Significant gain",
    "SIGNAL_REVERSAL": "Signal reversal",
    "CATALYST": "Catalyst detected",
}


def _type_label(alert_type: str) -> str:
    """Human-readable label for an alert type."""
    return _ALERT_TYPE_LABELS.get(alert_type, alert_type.replace("_", " ").title())
