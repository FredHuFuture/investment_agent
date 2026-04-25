"""MonitoringDaemon -- APScheduler-driven long-running daemon."""
from __future__ import annotations

import atexit
import asyncio
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Any

import aiosqlite

from daemon.config import DaemonConfig
from scripts.ensure_pid import (
    DEFAULT_PID_PATH,
    check_pid_file,
    ensure_pid_file,
    remove_pid_file,
)
from daemon.jobs import (
    run_catalyst_scan,
    run_daily_check,
    run_drift_detector,
    run_regime_detection,
    run_weekly_revaluation,
    reconcile_aborted_jobs,
    prune_signal_history,
)
from db.database import DEFAULT_DB_PATH, init_db


class MonitoringDaemon:
    """Long-running monitoring daemon with APScheduler.

    Scheduled jobs:
    - Daily check: Mon-Fri at configured hour (default 5 PM ET)
    - Weekly revaluation: configured day/hour (default Sat 10 AM ET)
    - Catalyst scan: stub (disabled until Task 017)
    """

    def __init__(self, config: DaemonConfig | None = None) -> None:
        self._config = config or DaemonConfig()
        self._logger: logging.Logger | None = None
        self._scheduler = None
        self._shutdown_event: asyncio.Event | None = None
        self._pid_file: Path = DEFAULT_PID_PATH
        self._start_time: float | None = None

    def _setup_logging(self) -> logging.Logger:
        """Configure file + console logging with JSON formatting (DATA-04).

        File: RotatingFileHandler (5 MB, 3 backups) -- structure preserved
        Console: stderr
        Format: JSON (JsonFormatter from api.log_format -- stdlib only, no new deps)
        """
        from api.log_format import JsonFormatter

        logger = logging.getLogger("investment_daemon")
        level = getattr(logging, self._config.log_level.upper(), logging.INFO)
        logger.setLevel(level)

        # Avoid duplicate handlers if called multiple times
        if logger.handlers:
            return logger

        fmt = JsonFormatter()

        # File handler (rotating)
        log_dir = os.path.dirname(self._config.log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            self._config.log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

        # Console handler (stderr)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(fmt)
        logger.addHandler(console_handler)

        return logger

    def _setup_scheduler(self) -> None:
        """Create AsyncIOScheduler and add cron jobs."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        self._scheduler = AsyncIOScheduler()

        # Daily check: Mon-Fri at configured time
        if self._config.daily_enabled:
            self._scheduler.add_job(
                self._job_daily,
                CronTrigger(
                    hour=self._config.daily_hour,
                    minute=self._config.daily_minute,
                    day_of_week=self._config.daily_days,
                    timezone=self._config.timezone,
                ),
                id="daily_check",
                name="Daily Portfolio Check",
            )

        # Weekly revaluation
        if self._config.weekly_enabled:
            self._scheduler.add_job(
                self._job_weekly,
                CronTrigger(
                    hour=self._config.weekly_hour,
                    minute=self._config.weekly_minute,
                    day_of_week=self._config.weekly_day,
                    timezone=self._config.timezone,
                ),
                id="weekly_revaluation",
                name="Weekly Deep Revaluation",
            )

        # Regime detection: Mon-Fri at configured time
        if self._config.regime_enabled:
            self._scheduler.add_job(
                self._job_regime,
                CronTrigger(
                    hour=self._config.regime_hour,
                    minute=self._config.regime_minute,
                    day_of_week="mon-fri",
                    timezone=self._config.timezone,
                ),
                id="regime_detection",
                name="Regime Detection",
            )

        # FOUND-06: Weekly signal_history pruning (every Sunday at 03:00)
        self._scheduler.add_job(
            self._job_prune,
            CronTrigger(
                day_of_week="sun",
                hour=3,
                minute=0,
                timezone=self._config.timezone,
            ),
            id="prune_signal_history",
            name="Signal History Pruning",
        )

        # AN-02 (Phase 7): IC-IR drift detector — Sunday 17:30 (before digest at 18:00)
        # misfire_grace_time=3600: if daemon was down at 17:30, fires within 1h window.
        self._scheduler.add_job(
            self._job_drift_detector,
            CronTrigger(
                day_of_week="sun",
                hour=17,
                minute=30,
                timezone=self._config.timezone,
            ),
            id="drift_detector",
            name="Signal Drift Detector",
            misfire_grace_time=3600,
        )

    async def _job_daily(self) -> None:
        """Scheduler wrapper for run_daily_check."""
        await run_daily_check(self._config.db_path, self._logger)

    async def _job_weekly(self) -> None:
        """Scheduler wrapper for run_weekly_revaluation."""
        await run_weekly_revaluation(self._config.db_path, self._logger)

    async def _job_regime(self) -> None:
        """Scheduler wrapper for run_regime_detection."""
        await run_regime_detection(self._config.db_path, self._logger)

    async def _job_prune(self) -> None:
        """Scheduler wrapper for prune_signal_history."""
        await prune_signal_history(
            self._config.db_path, retention_days=90, logger=self._logger
        )

    async def _job_drift_detector(self) -> None:
        """Scheduler wrapper for run_drift_detector (AN-02)."""
        await run_drift_detector(self._config.db_path, self._logger)

    async def start(self) -> None:
        """Start daemon (blocks until shutdown signal).

        1. PID file reconciliation (DATA-05)
        2. Setup logging
        3. Initialize DB schema
        4. Setup and start scheduler
        5. Log schedule summary
        6. Register signal handlers (POSIX only)
        7. Wait on shutdown event
        """
        import signal as signal_module
        import time as _time

        # DATA-05: Reconcile stale PID file before anything else.
        # Raises RuntimeError if another daemon is already running.
        state, existing_pid = check_pid_file(self._pid_file)
        if state == "ok":
            raise RuntimeError(
                f"Daemon already running (pid={existing_pid}); refusing to start"
            )
        if state == "stale":
            remove_pid_file(self._pid_file)

        ensure_pid_file(self._pid_file)
        atexit.register(remove_pid_file, self._pid_file)
        self._start_time = _time.monotonic()

        self._logger = self._setup_logging()
        self._logger.info("Investment monitoring daemon starting...")

        await init_db(self._config.db_path)
        self._logger.info("Database initialized: %s", self._config.db_path)

        # FOUND-07: Reconcile any stale 'running' job_run_log rows to 'aborted'
        # before starting the scheduler.  min_age_seconds=300 aligns with both
        # the /health STALE_RUNNING_SECONDS threshold (300s) and the run_once()
        # path (also 300s), preventing false-positive aborts of jobs that
        # legitimately run for several minutes.  The reconcile_aborted_jobs
        # default of 5s is intentionally kept for callers that want a tighter
        # sweep; this call site overrides it explicitly (WR-03 fix).
        aborted_count = await reconcile_aborted_jobs(
            self._config.db_path, min_age_seconds=300
        )
        if aborted_count > 0:
            self._logger.warning(
                "Reconciled %d stale 'running' job(s) to 'aborted'", aborted_count
            )

        self._setup_scheduler()
        self._scheduler.start()

        daily_status = (
            f"Mon-Fri {self._config.daily_hour:02d}:{self._config.daily_minute:02d} {self._config.timezone}"
            if self._config.daily_enabled else "DISABLED"
        )
        weekly_status = (
            f"{self._config.weekly_day} {self._config.weekly_hour:02d}:{self._config.weekly_minute:02d} {self._config.timezone}"
            if self._config.weekly_enabled else "DISABLED"
        )
        self._logger.info(
            "Scheduler started. Daily check: %s. Weekly revaluation: %s.",
            daily_status,
            weekly_status,
        )

        self._shutdown_event = asyncio.Event()

        # Register POSIX signal handlers (not available on Windows)
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal_module.SIGINT, signal_module.SIGTERM):
                loop.add_signal_handler(
                    sig, lambda: asyncio.create_task(self.stop())
                )

        try:
            await self._shutdown_event.wait()
        except KeyboardInterrupt:
            await self.stop()

    async def stop(self) -> None:
        """Graceful shutdown."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        if self._shutdown_event:
            self._shutdown_event.set()
        # DATA-05: Remove PID file on graceful shutdown.
        # atexit handler covers non-graceful exits (crashes, SIGKILL).
        remove_pid_file(self._pid_file)
        if self._logger:
            self._logger.info("Monitoring daemon stopped.")

    async def run_once(self, job_name: str) -> dict[str, Any]:
        """Run a single job immediately without the scheduler.

        Args:
            job_name: "daily" | "weekly"

        Used by CLI `run-once` subcommand.

        WR-01 fix: reconcile_aborted_jobs is called here (mirroring start())
        so that stale 'running' rows from a previous crashed run are cleaned up
        before this job inserts its own 'running' row.  min_age_seconds=300
        (5 min) avoids falsely aborting another run_once invocation that is
        still in flight — the old value of 5s was too short for jobs that can
        legitimately run for several minutes.
        """
        self._logger = self._setup_logging()
        await init_db(self._config.db_path)
        aborted_count = await reconcile_aborted_jobs(
            self._config.db_path, min_age_seconds=300
        )
        if aborted_count > 0 and self._logger:
            self._logger.warning(
                "run_once: reconciled %d stale 'running' job(s) to 'aborted'",
                aborted_count,
            )

        if job_name == "daily":
            return await run_daily_check(self._config.db_path, self._logger)
        elif job_name == "weekly":
            return await run_weekly_revaluation(self._config.db_path, self._logger)
        elif job_name == "regime":
            return await run_regime_detection(self._config.db_path, self._logger)
        elif job_name == "watchlist":
            from daemon.watchlist_job import run_watchlist_scan
            return await run_watchlist_scan(self._config.db_path, self._logger)
        elif job_name == "prune":
            return await prune_signal_history(
                self._config.db_path, retention_days=90, logger=self._logger
            )
        else:
            raise ValueError(f"Unknown job: {job_name!r}")

    async def get_status(self) -> dict[str, Any]:
        """Query daemon_runs for last run of each job type.

        Does NOT require scheduler to be running.

        Returns:
            {"daily_check": {...}, "weekly_revaluation": {...}, "catalyst_scan": {...}}
        """
        job_names = ["daily_check", "weekly_revaluation", "catalyst_scan", "regime_detection", "watchlist_scan"]
        result: dict[str, Any] = {}

        try:
            async with aiosqlite.connect(self._config.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                for job_name in job_names:
                    row = await (
                        await conn.execute(
                            """
                            SELECT job_name, status, started_at, duration_ms, result_json, error_message
                            FROM daemon_runs
                            WHERE job_name = ?
                            ORDER BY created_at DESC
                            LIMIT 1
                            """,
                            (job_name,),
                        )
                    ).fetchone()
                    if row:
                        result[job_name] = {
                            "last_run": row["started_at"],
                            "status": row["status"],
                            "duration_ms": row["duration_ms"],
                            "result_json": row["result_json"],
                            "error_message": row["error_message"],
                        }
                    else:
                        result[job_name] = {"last_run": None, "status": "never_run"}
        except Exception as exc:
            result["error"] = str(exc)

        return result
