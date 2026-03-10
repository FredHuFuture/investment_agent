# Task 010: Position Monitoring + Alert System

## 🎯 Goal

Implement a **rule-based position health checker** that scans all active portfolio positions, detects exit trigger conditions (stop loss, target price, time overrun, significant P&L), generates alerts, and saves portfolio snapshots. This is the "Daily Revaluation" from the architecture — **$0 cost, no LLM, pure data refresh and rule checks**.

Phase 1 scope: **one-shot CLI command** (not a daemon). Can be cron'd for scheduled execution.

## 📥 Context

- `portfolio/manager.py` (Task 003) — `PortfolioManager.load_portfolio()` returns `Portfolio` with positions.
- `portfolio/models.py` — `Position` with `holding_days`, `unrealized_pnl_pct`, `expected_hold_days`.
- `data_providers/` (Task 004) — `get_provider(asset_type)` for current prices.
- `db/database.py` — existing schema, needs `monitoring_alerts` table added.
- `project/investment_agent_v4_review.md` — identifies TIME_OVERRUN floor issue and missing index.
- Architecture: `docs/architecture_v4.md` §6.3 Daily Revaluation.

## 🛠️ Requirements

### 1. Schema Addition (`db/database.py`)

Add the `monitoring_alerts` table and index to `init_db`:

```python
await conn.execute(
    """
    CREATE TABLE IF NOT EXISTS monitoring_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL CHECK (
            severity IN ('CRITICAL', 'HIGH', 'WARNING', 'INFO')
        ),
        message TEXT NOT NULL,
        recommended_action TEXT,
        current_price REAL,
        trigger_price REAL,
        acknowledged INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)

await conn.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_ticker_time
    ON monitoring_alerts(ticker, created_at);
    """
)
```

### 2. Alert Model (`monitoring/models.py`)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class Alert:
    """A single monitoring alert for a position."""
    ticker: str
    alert_type: str      # STOP_LOSS_HIT | TARGET_HIT | TIME_OVERRUN | SIGNIFICANT_LOSS | SIGNIFICANT_GAIN
    severity: str        # CRITICAL | HIGH | WARNING | INFO
    message: str
    recommended_action: str
    current_price: float | None = None
    trigger_price: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "recommended_action": self.recommended_action,
            "current_price": self.current_price,
            "trigger_price": self.trigger_price,
        }
```

### 3. Position Health Checker (`monitoring/checker.py`)

Core logic for checking exit trigger conditions on a single position.

```python
from __future__ import annotations
from portfolio.models import Position
from monitoring.models import Alert

# Configurable thresholds
DEFAULT_HOLD_DAYS_FALLBACK = 90       # when expected_hold_days is NULL
TIME_OVERRUN_MULTIPLIER = 1.5
TIME_OVERRUN_MINIMUM_FLOOR = 7        # never fire TIME_OVERRUN before 7 days
SIGNIFICANT_LOSS_THRESHOLD = -0.15    # -15%
SIGNIFICANT_GAIN_THRESHOLD = 0.25     # +25%


def check_position(
    position: Position,
    current_price: float,
    expected_stop_loss: float | None = None,
    expected_target_price: float | None = None,
) -> list[Alert]:
    """Check a single position against all exit trigger rules.

    Args:
        position: Active position from portfolio.
        current_price: Latest market price.
        expected_stop_loss: Stop loss from original thesis (if any).
        expected_target_price: Target price from original thesis (if any).

    Returns:
        List of Alert objects (may be empty if position is healthy).
    """
```

**Alert rules (checked in priority order):**

1. **STOP_LOSS_HIT** (CRITICAL):
   - Condition: `expected_stop_loss is not None and current_price <= expected_stop_loss`
   - Message: `"{ticker} hit stop loss ${stop:.2f} (current: ${price:.2f}, loss: {pnl_pct:.1%})"`
   - Action: `"CLOSE POSITION — stop loss triggered"`

2. **TARGET_HIT** (INFO):
   - Condition: `expected_target_price is not None and current_price >= expected_target_price`
   - Message: `"{ticker} reached target ${target:.2f} (current: ${price:.2f}, gain: {pnl_pct:.1%})"`
   - Action: `"Consider taking profit — target reached"`

3. **TIME_OVERRUN** (WARNING):
   - Expected hold = `position.expected_hold_days or DEFAULT_HOLD_DAYS_FALLBACK`
   - Threshold = `max(expected_hold * TIME_OVERRUN_MULTIPLIER, TIME_OVERRUN_MINIMUM_FLOOR)`
   - Condition: `position.holding_days > threshold`
   - Message: `"{ticker} held {actual}d vs {expected}d expected ({multiplier:.1f}x overrun)"`
   - Action: `"Review: is the original thesis still intact?"`

4. **SIGNIFICANT_LOSS** (HIGH):
   - Compute `unrealized_pnl_pct = (current_price - position.avg_cost) / position.avg_cost`
   - Condition: `unrealized_pnl_pct < SIGNIFICANT_LOSS_THRESHOLD`
   - Do NOT fire if STOP_LOSS_HIT already fired (avoid duplicate alerts).
   - Message: `"{ticker} unrealized loss {pnl_pct:.1%} (current: ${price:.2f}, avg cost: ${cost:.2f})"`
   - Action: `"Review position — significant unrealized loss"`

5. **SIGNIFICANT_GAIN** (INFO):
   - Condition: `unrealized_pnl_pct > SIGNIFICANT_GAIN_THRESHOLD`
   - Do NOT fire if TARGET_HIT already fired.
   - Message: `"{ticker} unrealized gain {pnl_pct:.1%} (current: ${price:.2f}, avg cost: ${cost:.2f})"`
   - Action: `"Consider partial profit-taking"`

### 4. Alert Storage (`monitoring/store.py`)

```python
from __future__ import annotations
from pathlib import Path
import aiosqlite
from monitoring.models import Alert


class AlertStore:
    """Persist and query monitoring alerts."""

    def __init__(self, db: str | Path | aiosqlite.Connection) -> None:
        # Same connection-or-path pattern as DriftAnalyzer

    async def save_alert(self, alert: Alert) -> int:
        """Insert alert into monitoring_alerts. Returns alert id."""

    async def save_alerts(self, alerts: list[Alert]) -> list[int]:
        """Insert multiple alerts in a single transaction."""

    async def get_recent_alerts(
        self,
        ticker: str | None = None,
        limit: int = 20,
        severity: str | None = None,
    ) -> list[dict]:
        """Query recent alerts, optionally filtered by ticker/severity.

        Returns list of dicts with all alert fields + id + created_at.
        Ordered by created_at DESC.
        """

    async def get_alert_count(self, ticker: str | None = None, days: int = 7) -> int:
        """Count alerts in the last N days."""
```

### 5. Portfolio Monitor (`monitoring/monitor.py`)

Orchestrator that ties together: portfolio loading → price refresh → position checking → alert saving → snapshot saving.

```python
from __future__ import annotations
import json
from datetime import datetime, timezone

from data_providers.factory import get_provider
from db.database import DEFAULT_DB_PATH
from monitoring.checker import check_position
from monitoring.models import Alert
from monitoring.store import AlertStore
from portfolio.manager import PortfolioManager


class PortfolioMonitor:
    """One-shot portfolio health check.

    Loads portfolio, fetches current prices, checks all exit triggers,
    saves alerts, saves portfolio snapshot.
    """

    def __init__(self, db_path: str = str(DEFAULT_DB_PATH)) -> None:
        self._db_path = db_path

    async def run_check(self) -> dict:
        """Run full portfolio health check.

        Returns dict with:
            checked_positions: int
            alerts: list[dict]       # all alerts generated
            snapshot_saved: bool
            warnings: list[str]      # non-fatal issues (e.g. price fetch failed)
        """
```

**Implementation notes:**
- For each position, fetch current price via `get_provider(asset_type).get_current_price(ticker)`.
- To get `expected_stop_loss` and `expected_target_price`, query `positions_thesis` table using `position.original_analysis_id` (may be NULL for manually added positions → skip stop/target checks).
- Wrap the price refresh + check loop in a single DB transaction for snapshot consistency.
- If a price fetch fails for one position, log a warning and skip that position (don't crash the whole check).
- After all checks, save a portfolio snapshot to `portfolio_snapshots` with `trigger_event='daily_check'`.

### 6. Monitor CLI (`cli/monitor_cli.py`)

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portfolio monitoring commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check: run position health check
    check_parser = subparsers.add_parser("check", help="Run portfolio health check.")

    # alerts: show recent alerts
    alerts_parser = subparsers.add_parser("alerts", help="Show recent alerts.")
    alerts_parser.add_argument("--ticker", help="Filter by ticker.")
    alerts_parser.add_argument("--severity", choices=["CRITICAL", "HIGH", "WARNING", "INFO"])
    alerts_parser.add_argument("--limit", type=int, default=20)

    return parser
```

**`check` output format:**

```
================================================================
  PORTFOLIO HEALTH CHECK
  2026-03-10 16:30:00 UTC
================================================================

  Positions checked: 5
  Alerts generated:  2

  🔴 CRITICAL  AAPL — STOP_LOSS_HIT
     Hit stop loss $165.00 (current: $162.30, loss: -8.2%)
     → CLOSE POSITION — stop loss triggered

  🟡 WARNING   MSFT — TIME_OVERRUN
     Held 47d vs 30d expected (1.6x overrun)
     → Review: is the original thesis still intact?

  ✅ GOOGL, BTC, ETH — healthy

  Portfolio snapshot saved.
================================================================
```

**`alerts` output format:**

```
Recent Alerts (last 20):
  2026-03-10 16:30  CRITICAL  AAPL  STOP_LOSS_HIT   Hit stop loss $165.00...
  2026-03-10 16:30  WARNING   MSFT  TIME_OVERRUN     Held 47d vs 30d...
  2026-03-09 16:30  INFO      GOOGL TARGET_HIT       Reached target $180.00...
```

## 📝 Test Cases

### `tests/test_010_checker.py` (6 tests)

All tests use the `check_position` function directly — no DB, no mocks needed.

1. **test_stop_loss_alert**
   - Position with avg_cost=100, stop_loss=90. current_price=88.
   - Returns 1 CRITICAL alert, type=STOP_LOSS_HIT.

2. **test_target_hit_alert**
   - Position with avg_cost=100, target=120. current_price=125.
   - Returns 1 INFO alert, type=TARGET_HIT.

3. **test_time_overrun_alert**
   - Position with expected_hold_days=20, entry_date=60 days ago. current_price=105.
   - Returns 1 WARNING alert, type=TIME_OVERRUN.

4. **test_time_overrun_minimum_floor**
   - Position with expected_hold_days=2, entry_date=5 days ago.
   - Threshold = max(2 * 1.5, 7) = 7. holding_days=5 < 7 → **no alert**.
   - Verify empty list returned.

5. **test_significant_loss_no_stop**
   - Position with avg_cost=100, NO stop_loss. current_price=80 (−20%).
   - Returns 1 HIGH alert, type=SIGNIFICANT_LOSS.

6. **test_healthy_position_no_alerts**
   - Position with avg_cost=100, stop=90, target=120, expected_hold=30, entry=10 days ago. current_price=105.
   - All healthy → returns empty list.

### `tests/test_010_monitor.py` (4 tests)

Integration tests with mocked DataProviders and DB.

7. **test_monitor_run_check_with_alerts**
   - Set up DB with 2 positions (1 needs stop_loss alert, 1 healthy).
   - Mock `get_provider().get_current_price()` to return appropriate prices.
   - `run_check()` returns alerts for the bad position only.
   - Verify alerts saved to `monitoring_alerts` table.

8. **test_monitor_price_fetch_failure**
   - Mock one price fetch to raise Exception.
   - `run_check()` still succeeds, returns warning for failed ticker.
   - Other positions still checked.

9. **test_monitor_saves_snapshot**
   - Run check. Verify `portfolio_snapshots` table has a new row with `trigger_event='daily_check'`.

10. **test_alert_store_query**
    - Save 5 alerts (mixed tickers, severities).
    - `get_recent_alerts(ticker="AAPL")` returns only AAPL alerts.
    - `get_recent_alerts(severity="CRITICAL")` returns only CRITICAL alerts.

## 📂 Files

| Action | File |
|--------|------|
| CREATE | `monitoring/__init__.py` |
| CREATE | `monitoring/models.py` — Alert dataclass |
| CREATE | `monitoring/checker.py` — Position health check rules |
| CREATE | `monitoring/store.py` — Alert persistence + queries |
| CREATE | `monitoring/monitor.py` — PortfolioMonitor orchestrator |
| CREATE | `cli/monitor_cli.py` — CLI: check, alerts |
| MODIFY | `db/database.py` — Add monitoring_alerts table + index |
| CREATE | `tests/test_010_checker.py` — 6 checker tests |
| CREATE | `tests/test_010_monitor.py` — 4 integration tests |
| MODIFY | `pyproject.toml` — Add `monitoring` to hatch packages if needed |

## ✅ Acceptance Criteria

1. `pytest tests/test_010_checker.py tests/test_010_monitor.py -v` — all 10 tests pass.
2. `pytest tests/ -v` — full suite passes (73 existing + 10 new = 83, 2 skipped).
3. `python -m cli.monitor_cli check --help` works.
4. `monitoring_alerts` table created by `init_db`.
5. TIME_OVERRUN respects 7-day minimum floor.
6. Code follows PEP 8, type hints, `from __future__ import annotations`.

## ⚠️ Out of Scope

- Daemon/scheduler (continuous background process) → Phase 2
- Catalyst Scanner (LLM-based news analysis) → Phase 2
- Weekly Deep Revaluation (re-run full agent pipeline) → Phase 2
- Trailing stop logic (requires peak price tracking) → Phase 2
- Signal reversal detection → Phase 2
- Alert acknowledgement workflow → Phase 2
- Email/Slack notification dispatch → Phase 2

---
**Developer Agent instructions:**
Read `portfolio/models.py` and `portfolio/manager.py` (Task 003) for Position/Portfolio models. Read `db/database.py` for schema pattern. Read `data_providers/factory.py` for `get_provider()`. The `check_position` function should be **pure** (no I/O) — it takes a Position + price + thresholds and returns alerts. All I/O is in `PortfolioMonitor` and `AlertStore`. Run tests, report in `docs/AGENT_SYNC.md`, commit.
