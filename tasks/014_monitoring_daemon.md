# Task 014: Monitoring Daemon

## Goal

Wrap the existing one-shot monitoring and analysis pipeline into an APScheduler-driven daemon for continuous portfolio oversight. Scheduled jobs run daily (exit trigger checks) and weekly (full re-analysis with signal change detection). A catalyst scanner stub is included for future LLM integration (Task 017).

## Context

- `monitoring/monitor.py` (Task 010) -- `PortfolioMonitor.run_check()` does one-shot health check: loads portfolio, fetches prices, checks exit triggers, saves alerts + snapshot. Returns `{"checked_positions", "alerts", "snapshot_saved", "warnings"}`.
- `engine/pipeline.py` (Task 008) -- `AnalysisPipeline(db_path).analyze_ticker(ticker, asset_type, portfolio)` runs all agents, returns `AggregatedSignal`.
- `monitoring/store.py` (Task 010) -- `AlertStore(conn).save_alert(alert)` / `save_alerts(alerts)` persists `Alert` objects.
- `monitoring/models.py` (Task 010) -- `Alert(ticker, alert_type, severity, message, recommended_action, current_price, trigger_price)`.
- `tracking/store.py` (Task 011) -- `SignalStore(conn).save_signal(signal, thesis_id)` persists `AggregatedSignal` to `signal_history`.
- `portfolio/manager.py` (Task 003) -- `PortfolioManager(db_path).load_portfolio()` returns `Portfolio` with positions list.
- `portfolio/models.py` -- `Position` has `original_analysis_id: int | None` linking to `positions_thesis`.
- `db/database.py` -- `positions_thesis` table has `expected_signal TEXT`, `expected_confidence REAL`.
- `agents/models.py` -- `Signal` enum: BUY, HOLD, SELL.
- All async CLIs set `WindowsSelectorEventLoopPolicy` on Windows.
- No logging framework exists -- all output via print(). Daemon needs proper logging.

## Requirements

### 1. Schema Addition (`db/database.py`)

Add `daemon_runs` table for job execution auditing:

```python
# Task 014: daemon execution history
await conn.execute(
    """
    CREATE TABLE IF NOT EXISTS daemon_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_name TEXT NOT NULL,
        status TEXT NOT NULL CHECK (
            status IN ('success', 'error', 'skipped')
        ),
        started_at TEXT NOT NULL,
        duration_ms INTEGER NOT NULL,
        result_json TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)
await conn.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_daemon_runs_job_time
    ON daemon_runs(job_name, created_at);
    """
)
```

### 2. Package Structure

```
daemon/
    __init__.py              # Exports: MonitoringDaemon, DaemonConfig
    config.py                # DaemonConfig dataclass with schedule defaults
    signal_comparator.py     # Pure function: compare_signals() + SignalComparison
    jobs.py                  # Async job functions: daily, weekly, catalyst stub
    scheduler.py             # MonitoringDaemon class with APScheduler lifecycle
```

Add `daemon` to hatch packages in `pyproject.toml`.
Add `apscheduler>=3.10,<4.0` to dependencies in `pyproject.toml`.

**Important:** Use APScheduler 3.x (stable, mature `AsyncIOScheduler`). Do NOT use 4.x (alpha/rewrite).

### 3. DaemonConfig (`daemon/config.py`)

```python
from __future__ import annotations
from dataclasses import dataclass
from db.database import DEFAULT_DB_PATH

@dataclass
class DaemonConfig:
    """Configuration for the monitoring daemon."""
    db_path: str = str(DEFAULT_DB_PATH)

    # Daily check schedule (US/Eastern)
    daily_hour: int = 17          # 5 PM ET -- after market close
    daily_minute: int = 0
    daily_days: str = "mon-fri"   # APScheduler day_of_week format

    # Weekly revaluation schedule
    weekly_day: str = "sat"       # Saturday
    weekly_hour: int = 10         # 10 AM ET
    weekly_minute: int = 0

    # Catalyst scan (stub -- disabled until Task 017)
    catalyst_enabled: bool = False

    # Timezone
    timezone: str = "US/Eastern"

    # Logging
    log_file: str = "data/daemon.log"
    log_level: str = "INFO"
```

### 4. Signal Comparator (`daemon/signal_comparator.py`)

Pure function for comparing original thesis signal to current re-analysis signal. No I/O.

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class SignalComparison:
    """Result of comparing thesis signal to current analysis."""
    original_signal: str       # "BUY" | "HOLD" | "SELL"
    current_signal: str        # "BUY" | "HOLD" | "SELL"
    original_confidence: float
    current_confidence: float
    direction_reversed: bool   # BUY->SELL or SELL->BUY
    confidence_delta: float    # current - original

    @property
    def summary(self) -> str:
        if self.direction_reversed:
            return (
                f"REVERSAL: {self.original_signal} -> {self.current_signal} "
                f"(confidence: {self.original_confidence:.0f} -> {self.current_confidence:.0f})"
            )
        return (
            f"No change: {self.original_signal} -> {self.current_signal} "
            f"(confidence delta: {self.confidence_delta:+.0f})"
        )


def compare_signals(
    original_signal: str,
    original_confidence: float,
    current_signal: str,
    current_confidence: float,
) -> SignalComparison:
    """Compare original thesis signal to current re-analysis signal.

    A direction reversal is:
    - BUY -> SELL
    - SELL -> BUY

    BUY -> HOLD or SELL -> HOLD is a weakening, not a full reversal.
    HOLD -> BUY/SELL is a new directional signal, not a reversal.

    Args:
        original_signal: Signal string from positions_thesis.expected_signal
        original_confidence: From positions_thesis.expected_confidence
        current_signal: Signal string from new AggregatedSignal.final_signal.value
        current_confidence: From new AggregatedSignal.final_confidence

    Returns:
        SignalComparison with direction_reversed flag and metadata.
    """
    ...
```

### 5. Job Functions (`daemon/jobs.py`)

Three async functions, each self-contained. Never raise -- catch exceptions, log, record status.

**`run_daily_check(db_path: str, logger: logging.Logger) -> dict`**

1. Create `PortfolioMonitor(db_path)`
2. Call `await monitor.run_check()` (this already does everything: prices, checks, alerts, snapshot)
3. Log summary: positions checked, alerts generated, warnings
4. Record execution in `daemon_runs` via `_record_daemon_run()`
5. On exception: log error, record status="error" with error_message

**`run_weekly_revaluation(db_path: str, logger: logging.Logger) -> dict`**

1. Load portfolio: `PortfolioManager(db_path).load_portfolio()`
2. Create pipeline: `AnalysisPipeline(db_path=db_path)`
3. For each position in `portfolio.positions`:
   a. Run `await pipeline.analyze_ticker(position.ticker, position.asset_type)`
   b. Load original thesis: query `positions_thesis` for `expected_signal`, `expected_confidence` using `position.original_analysis_id`
   c. Call `compare_signals(original, new)` if thesis exists
   d. If `direction_reversed`: create `Alert(ticker, "SIGNAL_REVERSAL", "HIGH", message, action)` and save via `AlertStore`
   e. Save new signal via `SignalStore.save_signal(signal, thesis_id=position.original_analysis_id)`
   f. On per-position exception: log error, add to errors list, continue next position
4. Save portfolio snapshot with trigger_event="weekly_revaluation"
5. Record execution in `daemon_runs`
6. Return: `{"positions_analyzed", "signal_reversals", "alerts_generated", "signals_saved", "errors"}`

**`run_catalyst_scan_stub(db_path: str, logger: logging.Logger) -> dict`**

1. Log "Catalyst scanner not available -- requires LLM integration (Task 017)"
2. Record execution with status="skipped"
3. Return `{"status": "skipped", "reason": "LLM not integrated"}`

**`_record_daemon_run(db_path, job_name, status, duration_ms, result_json, error_message=None)`**

Insert row into `daemon_runs` table. Uses `aiosqlite.connect()`.

### 6. MonitoringDaemon (`daemon/scheduler.py`)

```python
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
        ...

    def _setup_scheduler(self) -> None:
        """Create AsyncIOScheduler and add cron/interval jobs."""
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
        """Wrapper that calls run_daily_check with logger and db_path."""
        await run_daily_check(self._config.db_path, self._logger)

    async def _job_weekly(self) -> None:
        """Wrapper that calls run_weekly_revaluation with logger and db_path."""
        await run_weekly_revaluation(self._config.db_path, self._logger)

    async def start(self) -> None:
        """Start daemon (blocks until shutdown signal).

        1. Setup logging
        2. Initialize DB schema (init_db)
        3. Setup and start scheduler
        4. Log schedule summary
        5. Register signal handlers
        6. Wait on shutdown event (blocks forever)
        """
        ...

    async def stop(self) -> None:
        """Graceful shutdown."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        if self._shutdown_event:
            self._shutdown_event.set()
        if self._logger:
            self._logger.info("Monitoring daemon stopped.")

    async def run_once(self, job_name: str) -> dict:
        """Run a single job immediately without scheduler.

        Args:
            job_name: "daily" or "weekly"

        Used by CLI `run-once` subcommand.
        """
        self._logger = self._setup_logging()
        await init_db(self._config.db_path)

        if job_name == "daily":
            return await run_daily_check(self._config.db_path, self._logger)
        elif job_name == "weekly":
            return await run_weekly_revaluation(self._config.db_path, self._logger)
        else:
            raise ValueError(f"Unknown job: {job_name}")

    async def get_status(self) -> dict:
        """Query daemon_runs for last run of each job type.

        Does NOT require scheduler to be running. Can be called anytime.

        Returns:
            {"daily_check": {"last_run", "status", "duration_ms"},
             "weekly_revaluation": {"last_run", "status", "duration_ms"},
             "catalyst_scan": {"last_run", "status"}}
        """
        ...
```

**Graceful shutdown:**

```python
# In start():
self._shutdown_event = asyncio.Event()

if sys.platform != "win32":
    loop = asyncio.get_running_loop()
    for sig in (signal_module.SIGINT, signal_module.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

try:
    await self._shutdown_event.wait()
except KeyboardInterrupt:
    await self.stop()
```

### 7. CLI (`cli/daemon_cli.py`)

```bash
# Start long-running daemon with default schedule
python -m cli.daemon_cli start

# Override schedule parameters
python -m cli.daemon_cli start --daily-hour 16 --weekly-day sun --weekly-hour 9 --timezone US/Pacific

# Override logging
python -m cli.daemon_cli start --log-file /var/log/investment_daemon.log --log-level DEBUG

# Run single job immediately, then exit
python -m cli.daemon_cli run-once daily
python -m cli.daemon_cli run-once weekly

# Show last run history for each job
python -m cli.daemon_cli status
```

**Parser structure:**

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="daemon_cli",
        description="Investment monitoring daemon -- scheduled portfolio checks.",
    )
    sub = parser.add_subparsers(dest="command")

    # start
    start_p = sub.add_parser("start", help="Start long-running daemon")
    start_p.add_argument("--daily-hour", type=int, default=17)
    start_p.add_argument("--weekly-day", type=str, default="sat")
    start_p.add_argument("--weekly-hour", type=int, default=10)
    start_p.add_argument("--timezone", type=str, default="US/Eastern")
    start_p.add_argument("--log-file", type=str, default="data/daemon.log")
    start_p.add_argument("--log-level", type=str, default="INFO",
                         choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    # run-once
    once_p = sub.add_parser("run-once", help="Run a single job, then exit")
    once_p.add_argument("job", choices=["daily", "weekly"])

    # status
    sub.add_parser("status", help="Show daemon run history")

    return parser
```

**Output format for `run-once daily`:**
Reuse existing monitor_cli output format -- print checked_positions, alerts summary, warnings.

**Output format for `run-once weekly`:**
```
================================================================
  WEEKLY REVALUATION
  2026-03-15 (3 positions analyzed)
================================================================

  AAPL:  BUY -> BUY   (confidence: 72 -> 68, delta: -4)  OK
  MSFT:  BUY -> SELL   (confidence: 65 -> 58, delta: -7)  ** REVERSAL **
  BTC-USD: HOLD -> HOLD (confidence: 45 -> 52, delta: +7)  OK

----------------------------------------------------------------
  ALERTS: 1 generated
  - [HIGH] MSFT: Signal reversed from BUY to SELL (confidence: 58)
----------------------------------------------------------------
  Signals saved: 3
  Errors: 0
================================================================
```

**Output format for `status`:**
```
================================================================
  DAEMON STATUS
================================================================
  Daily Check
    Last run:   2026-03-14 17:00:02 US/Eastern
    Status:     success
    Duration:   12.3s
    Positions:  5 checked, 1 alert

  Weekly Revaluation
    Last run:   2026-03-08 10:00:05 US/Eastern
    Status:     success
    Duration:   45.7s
    Positions:  5 analyzed, 0 reversals

  Catalyst Scan
    Status:     not configured (requires Task 017)
================================================================
```

**Windows event loop:**
```python
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

## Tests (`tests/test_014_daemon.py`)

10 test cases, all mocked (no network, no real scheduler, no APScheduler timing):

### Signal Comparator (pure, no mocks needed)

1. **`test_reversal_buy_to_sell`**: `compare_signals("BUY", 70.0, "SELL", 65.0)` -> `direction_reversed=True`, `confidence_delta=-5.0`
2. **`test_reversal_sell_to_buy`**: `compare_signals("SELL", 60.0, "BUY", 75.0)` -> `direction_reversed=True`, `confidence_delta=+15.0`
3. **`test_no_reversal_buy_to_hold`**: `compare_signals("BUY", 70.0, "HOLD", 50.0)` -> `direction_reversed=False`
4. **`test_no_reversal_same_signal`**: `compare_signals("BUY", 70.0, "BUY", 80.0)` -> `direction_reversed=False`, `confidence_delta=+10.0`

### Daily Job

5. **`test_daily_check_wraps_monitor`**: Setup DB with 2 positions. Mock `get_provider` to return price provider. Call `run_daily_check(db_path, logger)`. Assert `result["checked_positions"] >= 1`. Assert `daemon_runs` table has 1 row with `job_name="daily_check"`, `status="success"`.
6. **`test_daily_check_records_error`**: Mock `PortfolioMonitor.run_check` to raise `RuntimeError`. Call `run_daily_check()`. Assert `daemon_runs` has `status="error"`, `error_message` populated.

### Weekly Job

7. **`test_weekly_detects_reversal`**: Setup DB with 1 position (AAPL, `original_analysis_id=1`). Insert thesis row with `expected_signal="BUY"`, `expected_confidence=70.0`. Mock `AnalysisPipeline.analyze_ticker` to return `AggregatedSignal` with `final_signal=Signal.SELL`, `final_confidence=58.0`. Call `run_weekly_revaluation()`. Assert `result["signal_reversals"]` has 1 entry for AAPL. Assert `monitoring_alerts` has 1 row with `alert_type="SIGNAL_REVERSAL"`, `severity="HIGH"`. Assert `signal_history` has 1 new row.
8. **`test_weekly_no_reversal`**: Same setup but pipeline returns `Signal.BUY` (same direction). Assert `result["signal_reversals"]` is empty. Assert no SIGNAL_REVERSAL alerts.
9. **`test_weekly_handles_analysis_failure`**: 2 positions. Mock pipeline: AAPL raises exception, MSFT returns valid signal. Call `run_weekly_revaluation()`. Assert `result["positions_analyzed"] == 1`, `result["errors"]` has 1 entry for AAPL. Assert MSFT signal was saved.

### Catalyst Stub

10. **`test_catalyst_stub_records_skipped`**: Call `run_catalyst_scan_stub(db_path, logger)`. Assert `daemon_runs` has 1 row with `job_name="catalyst_scan"`, `status="skipped"`.

**Mocking strategy:**
- Use `tmp_path` for isolated DB per test
- Call `init_db(db_path)` at test start to create all tables
- Insert test positions/theses via direct SQL
- Mock `get_provider` for daily job (return AsyncMock with price)
- Mock `AnalysisPipeline.analyze_ticker` for weekly job (return crafted `AggregatedSignal`)
- Create a real `logging.Logger` pointing to `logging.NullHandler()` for tests

## Files

**CREATE (7):**
- `daemon/__init__.py`
- `daemon/config.py`
- `daemon/signal_comparator.py`
- `daemon/jobs.py`
- `daemon/scheduler.py`
- `cli/daemon_cli.py`
- `tests/test_014_daemon.py`

**MODIFY (2):**
- `db/database.py` -- add `daemon_runs` table + index in `init_db()`
- `pyproject.toml` -- add `apscheduler>=3.10,<4.0` to dependencies, add `"daemon"` to hatch packages

## Out of Scope

- Catalyst scanner implementation (Task 017, requires LLM)
- Email/push alert dispatch (Phase 2+ per architecture doc Section 6.6)
- Config file (YAML/TOML) -- CLI args are sufficient
- Systemd / Windows Service -- user runs manually or via OS scheduler
- WeeklyMonitoringReport class -- captured via daemon_runs result_json

## Verification

```bash
# Run tests
pytest tests/test_014_daemon.py -v

# Full suite (should be 125+ passed)
pytest tests/ -v

# Manual: run daily check
python -m cli.daemon_cli run-once daily

# Manual: run weekly revaluation
python -m cli.daemon_cli run-once weekly

# Manual: check status
python -m cli.daemon_cli status

# Manual: start daemon (Ctrl+C to stop)
python -m cli.daemon_cli start
```

## Hints

- `PortfolioMonitor.run_check()` already handles everything for the daily job -- just wrap it with logging + execution recording. Don't duplicate its logic.
- `AlertStore` can accept either a `str` db_path or an `aiosqlite.Connection`. For the weekly job where you already have a connection open, pass the connection directly.
- `SignalStore.save_signal()` accepts `AggregatedSignal` + optional `thesis_id`. The thesis_id links the new signal back to the original position thesis.
- `Position.original_analysis_id` links to `positions_thesis.id`. Use this to load the original signal/confidence for comparison.
- For the weekly job, use a single `aiosqlite.connect()` context for all position iterations to avoid connection churn. Create `AlertStore(conn)` and `SignalStore(conn)` once, reuse.
- APScheduler `CronTrigger` accepts `timezone` as a string (e.g., "US/Eastern"). It uses `pytz` internally.
- For tests, do NOT test APScheduler timing. Test the job functions directly as async functions.
- Use `logging.getLogger("investment_daemon")` as the logger name for consistency across daemon modules.
