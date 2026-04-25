"""Tests for daemon digest job and APScheduler Sunday 18:00 registration.

Test coverage:
  1. test_run_weekly_digest_writes_job_run_log          — job_run_log row after run
  2. test_apscheduler_registers_digest_weekly_sunday_1800 — cron fields + misfire
  3. test_run_weekly_digest_skips_email_when_not_configured — no crash when SMTP unset
  4. test_telegram_truncates_long_digest                — body >3900 chars gets truncated
"""
from __future__ import annotations

import pytest
import aiosqlite


# ---------------------------------------------------------------------------
# Fixture: initialized temp DB
# ---------------------------------------------------------------------------

@pytest.fixture
async def tmp_db_path(tmp_path):
    """Initialized temp DB."""
    db_path = str(tmp_path / "digest_scheduler_test.db")
    from db.database import init_db
    await init_db(db_path)
    return db_path


# ---------------------------------------------------------------------------
# Test 1: run_weekly_digest writes job_run_log with status='success'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_weekly_digest_writes_job_run_log(tmp_db_path):
    """After run_weekly_digest, job_run_log has a 'digest_weekly' success row."""
    from daemon.jobs import run_weekly_digest

    result = await run_weekly_digest(tmp_db_path)

    # Must not return error dict
    assert "error" not in result, f"run_weekly_digest returned error: {result.get('error')}"

    async with aiosqlite.connect(tmp_db_path) as conn:
        row = await (
            await conn.execute(
                """
                SELECT job_name, status FROM job_run_log
                WHERE job_name = 'digest_weekly'
                ORDER BY id DESC LIMIT 1
                """
            )
        ).fetchone()

    assert row is not None, "job_run_log must have a 'digest_weekly' row"
    assert row[0] == "digest_weekly"
    assert row[1] == "success"


# ---------------------------------------------------------------------------
# Test 2: APScheduler registers 'digest_weekly' job with correct cron fields
# ---------------------------------------------------------------------------

def test_apscheduler_registers_digest_weekly_sunday_1800(tmp_db_path):
    """MonitoringDaemon._setup_scheduler registers digest_weekly at Sunday 18:00."""
    from daemon.scheduler import MonitoringDaemon
    from daemon.config import DaemonConfig

    cfg = DaemonConfig(db_path=tmp_db_path)
    daemon = MonitoringDaemon(cfg)
    daemon._setup_scheduler()

    job = daemon._scheduler.get_job("digest_weekly")
    assert job is not None, "Job 'digest_weekly' must be registered in scheduler"

    # APScheduler CronTrigger stores fields; inspect by name
    fields_by_name = {f.name: str(f) for f in job.trigger.fields}

    day_of_week_val = fields_by_name.get("day_of_week", "")
    assert "sun" in day_of_week_val.lower(), (
        f"day_of_week must be 'sun', got: {day_of_week_val!r}"
    )

    hour_val = fields_by_name.get("hour", "")
    assert "18" in hour_val, f"hour must be 18, got: {hour_val!r}"

    minute_val = fields_by_name.get("minute", "")
    assert "0" in minute_val, f"minute must be 0, got: {minute_val!r}"

    assert job.misfire_grace_time == 3600, (
        f"misfire_grace_time must be 3600, got: {job.misfire_grace_time}"
    )


# ---------------------------------------------------------------------------
# Test 3: run_weekly_digest skips email gracefully when SMTP not configured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_weekly_digest_skips_email_when_not_configured(
    tmp_db_path, monkeypatch
):
    """run_weekly_digest returns success with email_sent=False when SMTP unset."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("ALERT_TO_EMAILS", raising=False)

    from daemon.jobs import run_weekly_digest

    result = await run_weekly_digest(tmp_db_path)

    assert "error" not in result, (
        f"Must not return error dict when SMTP unconfigured: {result}"
    )
    assert result["email_sent"] is False, (
        "email_sent must be False when SMTP not configured"
    )


# ---------------------------------------------------------------------------
# Test 4: Telegram truncates digest body longer than 3900 chars
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telegram_truncates_long_digest(tmp_db_path, monkeypatch):
    """When digest body >3900 chars, Telegram receives truncated body with marker."""
    from engine import digest as digest_module
    from notifications import telegram_dispatcher as tg_module

    # Patch render_weekly_digest to return a long body
    long_body = "## Header\n" + ("x" * 5000)

    async def fake_render(_db_path: str) -> str:
        return long_body

    monkeypatch.setattr(digest_module, "render_weekly_digest", fake_render)

    # Capture what TelegramDispatcher receives
    captured: dict[str, object] = {}

    class _FakeTelegramDispatcher:
        @property
        def is_configured(self) -> bool:
            return True

        async def send_alert_digest(self, alerts: list) -> bool:
            captured["body"] = alerts[0]["message"]
            return True

    monkeypatch.setattr(tg_module, "TelegramDispatcher", _FakeTelegramDispatcher)

    from daemon.jobs import run_weekly_digest

    await run_weekly_digest(tmp_db_path)

    assert "body" in captured, "TelegramDispatcher.send_alert_digest must have been called"
    body_sent = str(captured["body"])
    assert len(body_sent) <= 4000, (
        f"Telegram body must be <= 4000 chars, got {len(body_sent)}"
    )
    assert body_sent.endswith("...(truncated — full digest in email)"), (
        f"Truncated body must end with truncation marker, got: {body_sent[-60:]!r}"
    )
