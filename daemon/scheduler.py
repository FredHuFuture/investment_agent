"""MonitoringDaemon -- APScheduler-driven long-running daemon."""
from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import sys
from typing import Any

import aiosqlite

from daemon.config import DaemonConfig
from daemon.jobs import run_catalyst_scan_stub, run_daily_check, run_weekly_revaluation
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

    def _setup_logging(self) -> logging.Logger:
        """Configure file + console logging.

        File: RotatingFileHandler (5 MB, 3 backups)
        Console: stderr
        Format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        """
        logger = logging.getLogger("investment_daemon")
        level = getattr(logging, self._config.log_level.upper(), logging.INFO)
        logger.setLevel(level)

        # Avoid duplicate handlers if called multiple times
        if logger.handlers:
            return logger

        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

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

    async def _job_daily(self) -> None:
        """Scheduler wrapper for run_daily_check."""
        await run_daily_check(self._config.db_path, self._logger)

    async def _job_weekly(self) -> None:
        """Scheduler wrapper for run_weekly_revaluation."""
        await run_weekly_revaluation(self._config.db_path, self._logger)

    async def start(self) -> None:
        """Start daemon (blocks until shutdown signal).

        1. Setup logging
        2. Initialize DB schema
        3. Setup and start scheduler
        4. Log schedule summary
        5. Register signal handlers (POSIX only)
        6. Wait on shutdown event
        """
        import signal as signal_module

        self._logger = self._setup_logging()
        self._logger.info("Investment monitoring daemon starting...")

        await init_db(self._config.db_path)
        self._logger.info("Database initialized: %s", self._config.db_path)

        self._setup_scheduler()
        self._scheduler.start()

        self._logger.info(
            "Scheduler started. Daily check: Mon-Fri %02d:%02d %s. "
            "Weekly revaluation: %s %02d:%02d %s.",
            self._config.daily_hour,
            self._config.daily_minute,
            self._config.timezone,
            self._config.weekly_day,
            self._config.weekly_hour,
            self._config.weekly_minute,
            self._config.timezone,
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
        if self._logger:
            self._logger.info("Monitoring daemon stopped.")

    async def run_once(self, job_name: str) -> dict[str, Any]:
        """Run a single job immediately without the scheduler.

        Args:
            job_name: "daily" | "weekly"

        Used by CLI `run-once` subcommand.
        """
        self._logger = self._setup_logging()
        await init_db(self._config.db_path)

        if job_name == "daily":
            return await run_daily_check(self._config.db_path, self._logger)
        elif job_name == "weekly":
            return await run_weekly_revaluation(self._config.db_path, self._logger)
        else:
            raise ValueError(f"Unknown job: {job_name!r}")

    async def get_status(self) -> dict[str, Any]:
        """Query daemon_runs for last run of each job type.

        Does NOT require scheduler to be running.

        Returns:
            {"daily_check": {...}, "weekly_revaluation": {...}, "catalyst_scan": {...}}
        """
        job_names = ["daily_check", "weekly_revaluation", "catalyst_scan"]
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
