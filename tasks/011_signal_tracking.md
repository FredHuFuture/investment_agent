# Task 011: Signal Tracking + Confidence Calibration

## Goal

Implement a **signal history + accuracy tracking** system that persists every `AggregatedSignal` produced by the analysis pipeline, links signals to trade outcomes, and computes performance metrics (win rate, confidence calibration, per-agent accuracy). This is the "accountability ledger" — **$0 cost, no LLM, pure data tracking and statistics**.

Phase 1 scope: **record, resolve, query**. No learned-weight adaptation (Phase 2).

## Context

- `engine/aggregator.py` (Task 008) — `AggregatedSignal` with `to_dict()`, includes `agent_signals`, `metrics`, `warnings`.
- `engine/pipeline.py` (Task 008) — `AnalysisPipeline.analyze_ticker()` produces `AggregatedSignal`.
- `engine/drift_analyzer.py` (Task 002 + 008.5) — Drift analysis for existing trades. Signal tracking is **complementary** — drift tracks execution quality, signal tracking tracks prediction quality.
- `db/database.py` — existing schema, needs `signal_history` table added.
- `docs/architecture_v4.md` §5.3 — Confidence calibration chart, drift analysis engine.
- `project/investment_agent_v4_review.md` — Sparse calibration bucket warning (need `min_bucket_size` guard).

## Requirements

### 1. Schema Addition (`db/database.py`)

Add the `signal_history` table and indexes to `init_db`:

```python
await conn.execute(
    """
    CREATE TABLE IF NOT EXISTS signal_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        asset_type TEXT NOT NULL,
        final_signal TEXT NOT NULL CHECK (
            final_signal IN ('BUY', 'HOLD', 'SELL')
        ),
        final_confidence REAL NOT NULL,
        regime TEXT,
        raw_score REAL NOT NULL,
        consensus_score REAL NOT NULL,
        agent_signals_json TEXT NOT NULL,
        reasoning TEXT NOT NULL,
        warnings_json TEXT,
        thesis_id INTEGER,
        outcome TEXT CHECK (
            outcome IS NULL OR outcome IN ('WIN', 'LOSS', 'OPEN', 'SKIPPED')
        ),
        outcome_return_pct REAL,
        outcome_resolved_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (thesis_id) REFERENCES positions_thesis(id)
    );
    """
)

await conn.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_signal_history_ticker
    ON signal_history(ticker, created_at);
    """
)

await conn.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_signal_history_outcome
    ON signal_history(outcome, final_signal);
    """
)
```

**Outcome definitions:**
- `WIN`: BUY signal → positive return; SELL signal → negative return (avoided loss or shorted)
- `LOSS`: BUY signal → negative return; SELL signal → positive return (missed gain)
- `OPEN`: Trade entered but not yet resolved (position still open)
- `SKIPPED`: Signal was generated but no trade was entered
- `NULL`: Not yet evaluated

### 2. Signal Store (`tracking/store.py`)

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

import aiosqlite

from engine.aggregator import AggregatedSignal


class SignalStore:
    """Persist and query signal history."""

    def __init__(self, db: str | Path | aiosqlite.Connection) -> None:
        # Same connection-or-path pattern as DriftAnalyzer / AlertStore

    async def save_signal(
        self,
        signal: AggregatedSignal,
        thesis_id: int | None = None,
    ) -> int:
        """Persist an AggregatedSignal to signal_history.

        Extracts key fields from the signal for indexed columns.
        Stores agent_signals and warnings as JSON.

        Args:
            signal: The aggregated signal to save.
            thesis_id: Link to positions_thesis if a trade was entered.

        Returns:
            The signal_history row id.
        """

    async def resolve_outcome(
        self,
        signal_id: int,
        outcome: str,
        return_pct: float | None = None,
    ) -> None:
        """Update a signal's outcome after trade resolution.

        Args:
            signal_id: The signal_history row id.
            outcome: WIN | LOSS | OPEN | SKIPPED
            return_pct: Actual return percentage (if known).
        """

    async def resolve_from_thesis(self, thesis_id: int) -> None:
        """Auto-resolve outcome from trade_executions data.

        Looks up the signal_history row linked to this thesis_id.
        Queries trade_executions to determine if position is closed.
        If closed: computes actual return, sets WIN/LOSS based on signal direction.
        If still open: sets outcome='OPEN'.
        If no executions: sets outcome='SKIPPED'.
        """

    async def get_signal_history(
        self,
        ticker: str | None = None,
        signal: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Query recent signals, optionally filtered.

        Returns list of dicts with all signal_history fields.
        agent_signals_json and warnings_json are parsed back to Python objects.
        Ordered by created_at DESC.
        """

    async def get_resolved_signals(
        self,
        lookback: int = 100,
    ) -> list[dict[str, Any]]:
        """Get signals with non-NULL outcomes for accuracy computation.

        Only returns WIN/LOSS outcomes (excludes OPEN and SKIPPED).
        Ordered by created_at DESC.
        """
```

### 3. Signal Tracker (`tracking/tracker.py`)

Analytics engine that computes performance metrics from signal history.

```python
from __future__ import annotations
from typing import Any

from tracking.store import SignalStore


class SignalTracker:
    """Compute signal accuracy and agent performance metrics."""

    def __init__(self, store: SignalStore) -> None:
        self._store = store

    async def compute_accuracy_stats(
        self, lookback: int = 100
    ) -> dict[str, Any]:
        """Compute overall signal accuracy statistics.

        Returns:
            {
                "total_signals": int,       # all signals in lookback
                "resolved_count": int,       # WIN + LOSS count
                "win_count": int,
                "loss_count": int,
                "win_rate": float | None,    # win_count / resolved_count
                "avg_confidence": float | None,
                "by_signal": {
                    "BUY": {"count": int, "win_rate": float | None},
                    "SELL": {"count": int, "win_rate": float | None},
                    "HOLD": {"count": int, "win_rate": float | None},
                },
                "by_asset_type": {
                    "stock": {"count": int, "win_rate": float | None},
                    "btc": {"count": int, "win_rate": float | None},
                },
                "by_regime": {
                    "RISK_ON": {"count": int, "win_rate": float | None},
                    "RISK_OFF": {"count": int, "win_rate": float | None},
                    "NEUTRAL": {"count": int, "win_rate": float | None},
                },
            }
        """

    async def compute_calibration_data(
        self,
        lookback: int = 100,
        bucket_width: int = 10,
        min_bucket_size: int = 5,
    ) -> list[dict[str, Any]]:
        """Generate confidence calibration chart data.

        Groups resolved signals into confidence buckets (e.g., 30-40, 40-50, ..., 80-90).
        For each bucket, computes expected win rate (midpoint) vs actual win rate.

        Buckets with fewer than min_bucket_size samples are excluded
        (sparse bucket noise — see investment_agent_v4_review.md).

        Returns:
            [
                {
                    "confidence_bucket": "30-40",
                    "bucket_midpoint": 35.0,
                    "expected_win_rate": 35.0,
                    "actual_win_rate": 42.0,
                    "sample_size": 8,
                },
                ...
            ]

        Note: expected_win_rate = bucket_midpoint is a simplification.
        Ideal calibration: 70% confidence should win ~70% of the time.
        LLM systems tend to be overconfident → actual < expected.
        """

    async def compute_agent_performance(
        self, lookback: int = 100
    ) -> dict[str, dict[str, Any]]:
        """Compute per-agent accuracy metrics.

        Parses agent_signals_json from resolved signals.
        For each agent, computes:

        Returns:
            {
                "TechnicalAgent": {
                    "total_signals": int,
                    "agreement_rate": float,        # how often agent signal == final_signal
                    "directional_accuracy": float | None,  # see below
                    "avg_confidence": float,
                    "by_signal": {
                        "BUY": {"count": int, "accuracy": float | None},
                        "SELL": {"count": int, "accuracy": float | None},
                        "HOLD": {"count": int},
                    },
                },
                ...
            }

        Directional accuracy:
            - For BUY signals: % where outcome was WIN
            - For SELL signals: % where outcome was WIN (correctly warned)
            - HOLD signals don't have a directional prediction
            - Combined: weighted average of BUY and SELL accuracy
        """
```

### 4. Signal CLI (`cli/signal_cli.py`)

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Signal tracking commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # history: show recent signals
    history_parser = subparsers.add_parser("history", help="Show signal history.")
    history_parser.add_argument("--ticker", help="Filter by ticker.")
    history_parser.add_argument("--signal", choices=["BUY", "HOLD", "SELL"])
    history_parser.add_argument("--limit", type=int, default=20)

    # stats: show accuracy statistics
    stats_parser = subparsers.add_parser("stats", help="Show accuracy stats.")
    stats_parser.add_argument("--lookback", type=int, default=100)

    # calibration: show confidence calibration
    cal_parser = subparsers.add_parser("calibration", help="Show confidence calibration.")
    cal_parser.add_argument("--lookback", type=int, default=100)
    cal_parser.add_argument("--min-bucket", type=int, default=5)

    # agents: show per-agent performance
    agents_parser = subparsers.add_parser("agents", help="Show agent performance.")
    agents_parser.add_argument("--lookback", type=int, default=100)

    return parser
```

**`history` output format:**

```
Signal History (last 20):
  2026-03-10 16:30  BUY   72.0%  AAPL  stock  RISK_ON   → WIN   +8.2%
  2026-03-10 16:30  SELL  65.0%  MSFT  stock  NEUTRAL   → LOSS  +3.1%
  2026-03-09 14:00  BUY   58.0%  BTC   btc    RISK_ON   → OPEN    —
  2026-03-08 10:00  HOLD  45.0%  GOOGL stock  NEUTRAL   →  —      —
```

**`stats` output format:**

```
================================================================
  SIGNAL ACCURACY REPORT
  Last 100 signals
================================================================

  Resolved: 42 / 67 signals (25 pending/skipped)
  Win Rate: 61.9% (26 wins / 42 resolved)
  Avg Confidence: 62.3%

  By Signal:
    BUY   28 signals → 64.3% win rate
    SELL   8 signals → 50.0% win rate
    HOLD   6 signals → 66.7% win rate

  By Asset Type:
    stock  35 signals → 62.9% win rate
    btc     7 signals → 57.1% win rate

  By Regime:
    RISK_ON   18 signals → 72.2% win rate
    NEUTRAL   15 signals → 53.3% win rate
    RISK_OFF   9 signals → 55.6% win rate
================================================================
```

**`calibration` output format:**

```
================================================================
  CONFIDENCE CALIBRATION
  (ideal: expected ≈ actual)
================================================================

  Bucket      Expected   Actual   Samples   Delta
  ──────────  ────────   ──────   ───────   ─────
  30-40%       35.0%     42.0%       8      +7.0%
  40-50%       45.0%     38.0%      12      -7.0%
  50-60%       55.0%     52.0%      10      -3.0%
  60-70%       65.0%     58.0%       7      -7.0%  ← overconfident
  70-80%       75.0%     63.0%       5      -12.0% ← overconfident

  Interpretation:
    Delta > 0: under-confident (good — conservative)
    Delta < 0: over-confident (bad — predictions too rosy)

  ⚠ Buckets with < 5 samples excluded.
================================================================
```

**`agents` output format:**

```
================================================================
  AGENT PERFORMANCE
  Last 100 signals
================================================================

  TechnicalAgent:
    Signals: 42 | Agreement w/ final: 78.6%
    Directional accuracy: 62.5%
    Avg confidence: 64.2
    BUY: 24 (66.7% acc) | SELL: 10 (50.0% acc) | HOLD: 8

  FundamentalAgent:
    Signals: 35 | Agreement w/ final: 82.9%
    Directional accuracy: 65.0%
    Avg confidence: 58.7
    BUY: 20 (70.0% acc) | SELL: 8 (50.0% acc) | HOLD: 7

  MacroAgent:
    Signals: 42 | Agreement w/ final: 71.4%
    Directional accuracy: 55.0%
    Avg confidence: 55.1
    BUY: 18 (61.1% acc) | SELL: 12 (50.0% acc) | HOLD: 12
================================================================
```

### 5. Pipeline Integration Hook

**Do NOT modify `engine/pipeline.py` in this task.** Instead, document how to wire up signal saving:

The `PortfolioMonitor` (Task 010) and future CLI commands will call `SignalStore.save_signal()` after each analysis run. For Task 011 scope, signal saving is done manually via tests and can be wired into the pipeline in Phase 2.

The `resolve_from_thesis` method auto-resolves outcomes by querying trade_executions. This can be called from the monitoring daemon or a batch CLI command.

## Test Cases

### `tests/test_011_signal_store.py` (5 tests)

1. **test_save_and_query_signal**
   - Create an `AggregatedSignal` with known values.
   - `save_signal()` → returns signal_id.
   - `get_signal_history(ticker="AAPL")` → returns 1 row matching saved signal.
   - Verify all fields: ticker, asset_type, final_signal, final_confidence, regime, raw_score, consensus_score.
   - Verify agent_signals_json is properly parsed back to list.

2. **test_resolve_outcome**
   - Save a BUY signal with thesis_id=1.
   - `resolve_outcome(signal_id, "WIN", return_pct=0.08)`.
   - Query back → outcome="WIN", outcome_return_pct=0.08, outcome_resolved_at is not NULL.

3. **test_resolve_from_thesis**
   - Set up DB with: signal_history row (thesis_id=1, final_signal="BUY") + positions_thesis + trade_executions (BUY at $100, SELL at $110).
   - `resolve_from_thesis(thesis_id=1)`.
   - Query back → outcome="WIN", outcome_return_pct≈0.10.

4. **test_resolve_from_thesis_open_position**
   - Same setup but only BUY execution (no SELL).
   - `resolve_from_thesis(thesis_id=1)`.
   - Query back → outcome="OPEN", outcome_return_pct=None.

5. **test_resolve_from_thesis_no_executions**
   - Signal with thesis_id=1, but no trade_executions for thesis_id=1.
   - `resolve_from_thesis(thesis_id=1)`.
   - Query back → outcome="SKIPPED".

### `tests/test_011_signal_tracker.py` (5 tests)

6. **test_accuracy_stats_basic**
   - Insert 10 resolved signals: 6 WIN, 4 LOSS (mix of BUY/SELL).
   - `compute_accuracy_stats()`.
   - Verify: win_rate=0.6, resolved_count=10, win_count=6.
   - Verify by_signal breakdown is correct.

7. **test_accuracy_stats_by_asset_and_regime**
   - Insert signals across stock/btc and RISK_ON/NEUTRAL.
   - Verify by_asset_type and by_regime breakdowns.

8. **test_calibration_data**
   - Insert 30 signals with varied confidences (spread across 30-40, 50-60, 70-80 buckets).
   - `compute_calibration_data(min_bucket_size=5)`.
   - Verify bucket structure: confidence_bucket, bucket_midpoint, actual_win_rate, sample_size.
   - Verify: actual_win_rate = win_count / sample_size for each bucket.

9. **test_calibration_min_bucket_filter**
   - Insert signals: 10 in 50-60 bucket, 2 in 80-90 bucket.
   - `compute_calibration_data(min_bucket_size=5)`.
   - Verify 80-90 bucket is excluded (only 2 samples < 5 threshold).

10. **test_agent_performance**
    - Insert 5 resolved signals with known agent_signals_json.
    - `compute_agent_performance()`.
    - Verify: agreement_rate = (agent signal matched final_signal) / total.
    - Verify: directional_accuracy computed correctly for BUY/SELL agents.
    - Verify: avg_confidence matches expected value.

## Files

| Action | File |
|--------|------|
| CREATE | `tracking/__init__.py` |
| CREATE | `tracking/store.py` — Signal persistence + queries |
| CREATE | `tracking/tracker.py` — Accuracy analytics engine |
| CREATE | `cli/signal_cli.py` — CLI: history, stats, calibration, agents |
| MODIFY | `db/database.py` — Add signal_history table + indexes |
| CREATE | `tests/test_011_signal_store.py` — 5 store tests |
| CREATE | `tests/test_011_signal_tracker.py` — 5 tracker tests |

## Acceptance Criteria

1. `pytest tests/test_011_signal_store.py tests/test_011_signal_tracker.py -v` — all 10 tests pass.
2. `pytest tests/ -v` — full suite passes (73 existing + 10 new = 83, 2 skipped).
3. `python -m cli.signal_cli history --help` works.
4. `signal_history` table created by `init_db`.
5. Sparse calibration buckets filtered by `min_bucket_size`.
6. Code follows PEP 8, type hints, `from __future__ import annotations`.

## Out of Scope

- Automatic pipeline integration (saving signal on every `analyze_ticker` call) → Phase 2
- Learned weight adaptation based on agent_performance → Phase 2
- `agent_performance` materialized table (separate from signal_history) → Phase 2
- Regime-aware strategy switching → Phase 2
- React dashboard calibration chart rendering → Phase 2
- SHORT position outcome logic → Phase 2 (LONG only in Phase 1)
- Backtesting engine (historical signal replay) → Phase 2+

---
**Developer Agent instructions:**
Read `engine/aggregator.py` for `AggregatedSignal` and `to_dict()` structure. Read `engine/drift_analyzer.py` for the connection-or-path pattern. Read `db/database.py` for schema creation pattern. The `SignalTracker` analytics methods should be **pure computation** over query results — no I/O beyond what `SignalStore` provides. The `SignalStore` handles all DB interaction. `resolve_from_thesis` needs to query both `signal_history` and `trade_executions` tables. Run tests, report in `docs/AGENT_SYNC.md`, commit.
