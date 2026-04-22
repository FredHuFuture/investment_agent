"""GET /health endpoint.

Surfaces daemon and database state from job_run_log (FOUND-07).
No authentication; operator-visible only.

Response schema (frozen contract; DATA-04):
  {
    "data": {
      "status": "ok" | "degraded",
      "api_version": "0.2.0",
      "daemon": {
        "last_run": ISO8601 UTC | null,
        "last_run_job": str | null,
        "uptime_seconds": int | null,
        "jobs_last_24h": {"succeeded": int, "failed": int, "aborted": int},
        "stale_running": int,
        "pid_file_present": bool,
        "pid": int | null
      },
      "db": {"wal_mode": bool, "signal_history_rows": int}
    },
    "warnings": []
  }

uptime_seconds semantics (WR-01):
  Computed from the PID file mtime, which is set when the daemon writes its PID
  on startup.  This correctly reflects "daemon process age" rather than
  "oldest active job age".  Returns null when the PID file is absent (daemon
  not running) — distinguishing "daemon running but idle" (positive uptime)
  from "daemon not running" (null).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends

from api.deps import get_db_path

router = APIRouter()

API_VERSION = "0.2.0"
PID_FILE_PATH = Path("data/daemon.pid")
STALE_RUNNING_SECONDS = 300  # 5 minutes


@router.get("")
async def get_health(db_path: str = Depends(get_db_path)) -> dict:
    """Return daemon + DB health.

    Always returns HTTP 200 so external monitors can distinguish
    "api up, db sad" (degraded) from "api down" (no response at all).
    """
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(days=1)).isoformat()
    stale_cutoff = (now - timedelta(seconds=STALE_RUNNING_SECONDS)).isoformat()

    daemon_info: dict = {
        "last_run": None,
        "last_run_job": None,
        "uptime_seconds": None,
        "jobs_last_24h": {"succeeded": 0, "failed": 0, "aborted": 0},
        "stale_running": 0,
        "pid_file_present": False,
        "pid": None,
    }
    db_info: dict = {"wal_mode": False, "signal_history_rows": 0}

    try:
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row

            # 24-hour rolling counts by terminal status
            async with conn.execute(
                """
                SELECT status, COUNT(*) as n
                FROM job_run_log
                WHERE started_at >= ?
                  AND status IN ('success', 'error', 'aborted')
                GROUP BY status
                """,
                (day_ago,),
            ) as cursor:
                async for row in cursor:
                    if row["status"] == "success":
                        daemon_info["jobs_last_24h"]["succeeded"] = int(row["n"])
                    elif row["status"] == "error":
                        daemon_info["jobs_last_24h"]["failed"] = int(row["n"])
                    elif row["status"] == "aborted":
                        daemon_info["jobs_last_24h"]["aborted"] = int(row["n"])

            # Last completed run (success or error -- not running/aborted)
            async with conn.execute(
                """
                SELECT job_name, started_at
                FROM job_run_log
                WHERE status IN ('success', 'error')
                ORDER BY started_at DESC
                LIMIT 1
                """
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    daemon_info["last_run"] = row["started_at"]
                    daemon_info["last_run_job"] = row["job_name"]

            # Stale running: status='running' AND started_at older than STALE_RUNNING_SECONDS
            async with conn.execute(
                """
                SELECT COUNT(*) as n FROM job_run_log
                WHERE status = 'running' AND started_at < ?
                """,
                (stale_cutoff,),
            ) as cursor:
                row = await cursor.fetchone()
                daemon_info["stale_running"] = int(row["n"]) if row else 0

            # uptime_seconds: derived from PID file mtime (WR-01 fix).
            # The daemon writes its PID file on startup, so mtime ≈ daemon start time.
            # This correctly returns a positive value when the daemon is idle (no
            # active jobs in job_run_log), unlike the previous MIN(started_at) query
            # which returned null between job runs.  Populated below after the DB
            # block, alongside the other PID-file reads.

            # signal_history row count
            async with conn.execute(
                "SELECT COUNT(*) as n FROM signal_history"
            ) as cursor:
                row = await cursor.fetchone()
                db_info["signal_history_rows"] = int(row["n"]) if row else 0

            # WAL mode check
            async with conn.execute("PRAGMA journal_mode") as cursor:
                row = await cursor.fetchone()
                db_info["wal_mode"] = row is not None and str(row[0]).lower() == "wal"

    except Exception:
        # Return 200 with degraded status so monitors can detect API-up vs DB-down
        return {
            "data": {
                "status": "degraded",
                "api_version": API_VERSION,
                "daemon": daemon_info,
                "db": db_info,
            },
            "warnings": ["Failed to query DB for health snapshot."],
        }

    # PID file inspection (filesystem; outside DB block).
    # uptime_seconds is computed here from PID file mtime (WR-01 fix):
    # - daemon present (pid file exists) → uptime = now - mtime (positive even when idle)
    # - daemon absent (no pid file)      → uptime = null
    try:
        if PID_FILE_PATH.exists():
            daemon_info["pid_file_present"] = True
            pid_text = PID_FILE_PATH.read_text().strip()
            try:
                daemon_info["pid"] = int(pid_text)
            except ValueError:
                pass
            # Derive uptime from PID file modification time (set when daemon starts).
            try:
                mtime = os.path.getmtime(PID_FILE_PATH)
                pid_created = datetime.fromtimestamp(mtime, tz=timezone.utc)
                daemon_info["uptime_seconds"] = int((now - pid_created).total_seconds())
            except (OSError, ValueError):
                pass
    except Exception:
        pass

    return {
        "data": {
            "status": "ok",
            "api_version": API_VERSION,
            "daemon": daemon_info,
            "db": db_info,
        },
        "warnings": [],
    }
