"""Tests for POST /digest/weekly endpoint and EmailDispatcher.send_markdown_email.

Test coverage:
  1. test_post_digest_weekly_returns_markdown    — 200 + text/markdown + all 5 H2 headers
  2. test_post_digest_weekly_no_dollar_amounts   — PII regression: no $NNN in response body
  3. test_send_markdown_email_uses_pre_wrap      — <pre> wraps body in HTML
  4. test_send_markdown_email_skips_when_not_configured — returns False gracefully
  5. test_send_markdown_email_html_escapes_script_tags  — <script> → &lt;script&gt;
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def app_db(tmp_path):
    """Create an initialized temp DB for test app."""
    db_path = str(tmp_path / "digest_email_test.db")
    from db.database import init_db
    await init_db(db_path)
    return db_path


@pytest.fixture
def test_app(app_db):
    """FastAPI TestClient with temp DB injected."""
    from fastapi.testclient import TestClient
    from api.app import create_app
    client_app = create_app(db_path=app_db)
    return TestClient(client_app)


# ---------------------------------------------------------------------------
# Test 1: POST /digest/weekly → 200 text/markdown with all 5 H2 headers
# ---------------------------------------------------------------------------

def test_post_digest_weekly_returns_markdown(test_app):
    """POST /digest/weekly returns 200 with text/markdown and all 5 required H2 headers."""
    response = test_app.post("/digest/weekly")
    assert response.status_code == 200
    assert "text/markdown" in response.headers.get("content-type", "")

    body = response.text
    assert len(body) >= 100, "Digest body should be non-trivial"

    # All 5 H2 headers must be present
    for header in [
        "## Portfolio Performance vs Benchmark",
        "## Top 5 Signal Flips This Week",
        "## IC-IR Movers",
        "## Open Thesis Drift Alerts",
        "## Action Items",
    ]:
        assert header in body, f"Missing H2 header: {header!r}"


# ---------------------------------------------------------------------------
# Test 2: PII regression — no dollar amounts in response body
# ---------------------------------------------------------------------------

def test_post_digest_weekly_no_dollar_amounts(test_app):
    """POST /digest/weekly response body must not contain raw dollar amounts."""
    import re
    response = test_app.post("/digest/weekly")
    assert response.status_code == 200
    body = response.text
    dollar_matches = re.findall(r"\$[0-9,]+", body)
    assert dollar_matches == [], (
        f"Dollar amount pattern found in /digest/weekly response: {dollar_matches}"
    )


# ---------------------------------------------------------------------------
# Test 3: send_markdown_email wraps body in <pre>
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_markdown_email_uses_pre_wrap(monkeypatch):
    """send_markdown_email calls _send_async with HTML body containing <pre>."""
    from notifications.email_dispatcher import EmailDispatcher, EmailConfig

    captured: dict[str, str] = {}

    async def fake_send_async(self: EmailDispatcher, subject: str, html_body: str) -> bool:
        captured["subject"] = subject
        captured["html"] = html_body
        return True

    monkeypatch.setattr(EmailDispatcher, "_send_async", fake_send_async)

    cfg = EmailConfig(
        smtp_host="smtp.test",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        from_address="from@test",
        to_addresses=["to@test"],
    )
    dispatcher = EmailDispatcher(config=cfg)
    result = await dispatcher.send_markdown_email("Test Digest", "## H\n\nBody")

    assert result is True
    assert "<pre>" in captured["html"], "HTML body must contain <pre> wrapper"
    # Markdown content must be present (escaped)
    assert "## H" in captured["html"] or "Body" in captured["html"]


# ---------------------------------------------------------------------------
# Test 4: send_markdown_email returns False when not configured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_markdown_email_skips_when_not_configured(monkeypatch):
    """send_markdown_email returns False (not raises) when SMTP not configured."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("ALERT_TO_EMAILS", raising=False)

    from notifications.email_dispatcher import EmailDispatcher

    # Force config reload without SMTP_HOST
    dispatcher = EmailDispatcher(config=None)
    # Manually ensure config is None (env var was deleted)
    dispatcher._config = None

    result = await dispatcher.send_markdown_email("Subject", "## body")
    assert result is False, "Must return False when not configured, not raise"


# ---------------------------------------------------------------------------
# Test 5: send_markdown_email HTML-escapes script injection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_markdown_email_html_escapes_script_tags(monkeypatch):
    """Markdown body with <script> tags → HTML body contains &lt;script&gt;."""
    from notifications.email_dispatcher import EmailDispatcher, EmailConfig

    captured: dict[str, str] = {}

    async def fake_send_async(self: EmailDispatcher, subject: str, html_body: str) -> bool:
        captured["html"] = html_body
        return True

    monkeypatch.setattr(EmailDispatcher, "_send_async", fake_send_async)

    cfg = EmailConfig(
        smtp_host="smtp.test",
        smtp_port=587,
        smtp_user="",
        smtp_password="",
        from_address="f",
        to_addresses=["t@t"],
    )
    dispatcher = EmailDispatcher(config=cfg)
    await dispatcher.send_markdown_email("S", "<script>alert(1)</script>")

    assert "&lt;script&gt;" in captured["html"], (
        "Script tag must be HTML-escaped in email body"
    )
    assert "<script>alert(1)</script>" not in captured["html"], (
        "Raw <script> tag must not appear in email HTML"
    )
