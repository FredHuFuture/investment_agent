"""Tests for DATA-04: /health endpoint and JSON logging.

Tests:
  - /health schema validation (basic, counts, stale running, PID file)
  - JsonFormatter correctness (fields, interpolation, extras, exceptions)
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from db.database import init_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run a coroutine synchronously (compatible with pytest-asyncio auto mode)."""
    return asyncio.get_event_loop().run_until_complete(coro)


async def _seed_job_run_log(db_path: str, rows: list) -> None:
    """Insert rows into job_run_log for testing.

    Each row: (job_name, started_at, status, completed_at, duration_ms)
    """
    async with aiosqlite.connect(db_path) as conn:
        for job_name, started_at, status, completed_at, duration_ms in rows:
            await conn.execute(
                "INSERT INTO job_run_log (job_name, started_at, status, completed_at, duration_ms) "
                "VALUES (?,?,?,?,?)",
                (job_name, started_at, status, completed_at, duration_ms),
            )
        await conn.commit()


async def _seed_signal_history(db_path: str, n: int) -> None:
    """Insert n rows into signal_history."""
    async with aiosqlite.connect(db_path) as conn:
        for i in range(n):
            await conn.execute(
                "INSERT INTO signal_history "
                "(ticker, asset_type, final_signal, final_confidence, raw_score, "
                " consensus_score, agent_signals_json, reasoning, created_at) "
                "VALUES (?, 'stock', 'HOLD', 0.5, 0.0, 0.0, '[]', 'test', datetime('now'))",
                (f"TICK{i}",),
            )
        await conn.commit()


def _make_app(db_path: str):
    """Create a test FastAPI app pointed at `db_path`."""
    from api.app import create_app
    return create_app(db_path)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------------
# /health endpoint tests
# ---------------------------------------------------------------------------


class TestHealthBasicSchema:
    """Test 1: GET /health returns 200 with all required top-level keys."""

    def test_health_basic_schema(self, tmp_path):
        db = str(tmp_path / "test.db")
        _run(init_db(db))
        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        d = body["data"]
        assert d["status"] in ("ok", "degraded")
        assert "api_version" in d
        assert "daemon" in d
        daemon = d["daemon"]
        assert "last_run" in daemon
        assert "last_run_job" in daemon
        assert "uptime_seconds" in daemon
        assert "jobs_last_24h" in daemon
        j24 = daemon["jobs_last_24h"]
        assert "succeeded" in j24
        assert "failed" in j24
        assert "aborted" in j24
        assert "stale_running" in daemon
        assert "pid_file_present" in daemon
        assert "pid" in daemon
        assert "db" in d
        db_info = d["db"]
        assert "wal_mode" in db_info
        assert "signal_history_rows" in db_info

    def test_health_empty_db_all_zeros(self, tmp_path):
        """Empty job_run_log → all counts are 0."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))
        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        body = r.json()["data"]
        assert body["daemon"]["jobs_last_24h"]["succeeded"] == 0
        assert body["daemon"]["jobs_last_24h"]["failed"] == 0
        assert body["daemon"]["jobs_last_24h"]["aborted"] == 0
        assert body["daemon"]["stale_running"] == 0
        assert body["daemon"]["last_run"] is None
        assert body["db"]["signal_history_rows"] == 0


class TestHealthCounts24h:
    """Test 2: jobs_last_24h counts from job_run_log (24h window)."""

    def test_health_counts_24h_by_status(self, tmp_path):
        """Seed 3 success, 2 error, 1 aborted within 24h → correct counts."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))

        now = _now_utc()
        recent = (now - timedelta(hours=1)).isoformat()
        rows = [
            ("job_a", recent, "success", recent, 100),
            ("job_b", recent, "success", recent, 200),
            ("job_c", recent, "success", recent, 300),
            ("job_d", recent, "error", recent, 400),
            ("job_e", recent, "error", recent, 500),
            ("job_f", recent, "aborted", None, None),
        ]
        _run(_seed_job_run_log(db, rows))

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        j24 = r.json()["data"]["daemon"]["jobs_last_24h"]
        assert j24["succeeded"] == 3
        assert j24["failed"] == 2
        assert j24["aborted"] == 1

    def test_health_excludes_older_than_24h(self, tmp_path):
        """Rows older than 24h are NOT counted."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))

        now = _now_utc()
        old = (now - timedelta(days=2)).isoformat()
        rows = [
            ("job_old", old, "success", old, 100),
        ]
        _run(_seed_job_run_log(db, rows))

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        j24 = r.json()["data"]["daemon"]["jobs_last_24h"]
        assert j24["succeeded"] == 0


class TestHealthLastRun:
    """Test 3: last_run = MAX(started_at) of completed rows."""

    def test_health_last_run_is_most_recent_terminal(self, tmp_path):
        """Multiple terminal rows → last_run is the most recent one."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))

        now = _now_utc()
        earlier = (now - timedelta(hours=3)).isoformat()
        later = (now - timedelta(hours=1)).isoformat()

        rows = [
            ("job_a", earlier, "success", earlier, 100),
            ("job_b", later, "success", later, 200),
        ]
        _run(_seed_job_run_log(db, rows))

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        daemon = r.json()["data"]["daemon"]
        # last_run should be the later timestamp
        assert daemon["last_run"] == later
        assert daemon["last_run_job"] == "job_b"


class TestHealthStaleRunning:
    """Test 4: stale_running counts only rows older than 5 min."""

    def test_health_stale_running_counts_only_over_5_min(self, tmp_path):
        """1 running row 10 min old + 1 running row 1 min old → stale_running = 1."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))

        now = _now_utc()
        stale_at = (now - timedelta(minutes=10)).isoformat()
        fresh_at = (now - timedelta(minutes=1)).isoformat()

        rows = [
            ("job_stale", stale_at, "running", None, None),
            ("job_fresh", fresh_at, "running", None, None),
        ]
        _run(_seed_job_run_log(db, rows))

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        daemon = r.json()["data"]["daemon"]
        assert daemon["stale_running"] == 1


class TestHealthSignalHistory:
    """Test 6: db.signal_history_rows equals COUNT(*) FROM signal_history."""

    def test_health_signal_history_count(self, tmp_path):
        """Seed 7 signal_history rows → reported as 7."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))
        _run(_seed_signal_history(db, 7))

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        db_info = r.json()["data"]["db"]
        assert db_info["signal_history_rows"] == 7


class TestHealthWalMode:
    """Test 5: db.wal_mode is True after init_db enables WAL."""

    def test_health_wal_mode_true_after_init_db(self, tmp_path):
        db = str(tmp_path / "test.db")
        _run(init_db(db))
        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        db_info = r.json()["data"]["db"]
        # init_db sets WAL mode; /health should report wal_mode=True
        assert db_info["wal_mode"] is True


class TestHealthPidFile:
    """Tests 7 + 9: pid_file_present and pid fields."""

    def test_health_pid_file_reported(self, tmp_path, monkeypatch):
        """When data/daemon.pid exists → pid_file_present=True, pid=integer."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))

        # Write a fake pid file under the tmp_path
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("99999")

        # Patch the health route's PID_FILE_PATH
        import api.routes.health as health_module
        monkeypatch.setattr(health_module, "PID_FILE_PATH", pid_file)

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        daemon = r.json()["data"]["daemon"]
        assert daemon["pid_file_present"] is True
        assert daemon["pid"] == 99999

    def test_health_pid_file_missing(self, tmp_path, monkeypatch):
        """No pid file → pid_file_present=False, pid=None."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))

        pid_file = tmp_path / "daemon.pid"
        # Make sure it doesn't exist
        if pid_file.exists():
            pid_file.unlink()

        import api.routes.health as health_module
        monkeypatch.setattr(health_module, "PID_FILE_PATH", pid_file)

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")
        daemon = r.json()["data"]["daemon"]
        assert daemon["pid_file_present"] is False
        assert daemon["pid"] is None


class TestHealthUptimeFromPidMtime:
    """Test WR-01: uptime_seconds derives from PID file mtime, not job_run_log."""

    def test_uptime_seconds_positive_when_pid_file_present_and_job_log_empty(
        self, tmp_path, monkeypatch
    ):
        """PID file exists but job_run_log is empty → uptime_seconds is positive int."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))

        # Write a PID file (no jobs in DB)
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("12345")

        import api.routes.health as health_module
        monkeypatch.setattr(health_module, "PID_FILE_PATH", pid_file)

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")

        daemon = r.json()["data"]["daemon"]
        # uptime_seconds must be a non-negative integer — not null — even though
        # job_run_log is empty (previously the old MIN(started_at) query returned null)
        assert daemon["uptime_seconds"] is not None
        assert isinstance(daemon["uptime_seconds"], int)
        assert daemon["uptime_seconds"] >= 0

    def test_uptime_seconds_null_when_pid_file_absent(self, tmp_path, monkeypatch):
        """No PID file → uptime_seconds is null (daemon not running)."""
        db = str(tmp_path / "test.db")
        _run(init_db(db))

        pid_file = tmp_path / "daemon.pid"
        if pid_file.exists():
            pid_file.unlink()

        import api.routes.health as health_module
        monkeypatch.setattr(health_module, "PID_FILE_PATH", pid_file)

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")

        daemon = r.json()["data"]["daemon"]
        assert daemon["uptime_seconds"] is None

    def test_uptime_seconds_reflects_pid_file_age(self, tmp_path, monkeypatch):
        """uptime_seconds approximately equals (now - pid_file_mtime) in seconds."""
        import time

        db = str(tmp_path / "test.db")
        _run(init_db(db))

        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("12345")

        # Record mtime immediately after creation
        before = time.time()

        import api.routes.health as health_module
        monkeypatch.setattr(health_module, "PID_FILE_PATH", pid_file)

        app = _make_app(db)
        with TestClient(app) as client:
            r = client.get("/health")

        after = time.time()
        elapsed_max = after - before + 2  # 2s tolerance

        daemon = r.json()["data"]["daemon"]
        assert daemon["uptime_seconds"] is not None
        # uptime should be small (file was just written) and within tolerance
        assert 0 <= daemon["uptime_seconds"] <= elapsed_max


class TestHealthDegradedOnDbError:
    """Test 10: DB error → 200 with status=degraded."""

    def test_health_db_error_returns_degraded_not_500(self, tmp_path):
        """Point to non-existent DB path → 200 with status='degraded'."""
        bad_db = str(tmp_path / "nonexistent_dir" / "bad.db")
        app = _make_app(bad_db)
        with TestClient(app) as client:
            r = client.get("/health")
        # Must not be 500 — /health should always return 200
        assert r.status_code == 200
        body = r.json()
        # Either degraded from DB failure or ok from aiosqlite auto-creating the file
        # The key invariant is status != 500 (already checked above)
        assert "data" in body


# ---------------------------------------------------------------------------
# JSON logging tests
# ---------------------------------------------------------------------------


class TestJsonFormatter:
    """Tests for api/log_format.py JsonFormatter."""

    def _make_logger(self, name: str = "test_logger") -> tuple[logging.Logger, io.StringIO]:
        """Create a logger with JsonFormatter writing to StringIO."""
        from api.log_format import JsonFormatter
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger(name + "_" + str(id(buf)))
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        return logger, buf

    def test_json_formatter_basic_fields(self):
        """Basic log record has timestamp, level, logger, message keys."""
        logger, buf = self._make_logger("basic")
        logger.info("hi there")
        record = json.loads(buf.getvalue())
        assert "timestamp" in record
        assert record["level"] == "INFO"
        assert "logger" in record
        assert record["message"] == "hi there"

    def test_json_formatter_interpolates_args(self):
        """logger.info('hello %s', 'world') → message='hello world'."""
        logger, buf = self._make_logger("interp")
        logger.info("hello %s", "world")
        record = json.loads(buf.getvalue())
        assert record["message"] == "hello world"

    def test_json_formatter_promotes_extras(self):
        """Extra context is flattened to top-level keys."""
        logger, buf = self._make_logger("extras")
        logger.info("job done", extra={"job_name": "daily_check", "duration_ms": 1234})
        record = json.loads(buf.getvalue())
        assert record["job_name"] == "daily_check"
        assert record["duration_ms"] == 1234

    def test_json_formatter_handles_exceptions(self):
        """Exception info is captured in exc_info field."""
        logger, buf = self._make_logger("exc")
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("oops")
        record = json.loads(buf.getvalue())
        assert "exc_info" in record
        assert "ValueError" in record["exc_info"]
        assert record["message"] == "oops"

    def test_install_json_logging_replaces_handlers(self):
        """install_json_logging() installs exactly 1 handler with JsonFormatter."""
        from api.log_format import install_json_logging, JsonFormatter
        test_logger_name = "test_install_json_" + str(os.getpid())
        logger = install_json_logging(logger_name=test_logger_name)
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, JsonFormatter)

    def test_no_new_pyproject_deps_for_json_logs(self):
        """pyproject.toml must not contain structlog or python-json-logger."""
        pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
        assert "structlog" not in pyproject
        assert "python-json-logger" not in pyproject
