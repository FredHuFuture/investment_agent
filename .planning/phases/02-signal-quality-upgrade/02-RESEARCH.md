# Phase 2: Signal Quality Upgrade - Research

**Researched:** 2026-04-21
**Domain:** Signal calibration (Brier, IC/ICIR), tail risk (CVaR, portfolio VaR), backtesting rigour (transaction costs, walk-forward)
**Confidence:** HIGH for SIG-01/04/06 (direct code inspection + PyPI verification). MEDIUM for SIG-02/03/05 (well-established theory, integration surfaces verified).

---

## Decision Summary Table

| # | Research Question | Concrete Recommendation | Confidence |
|---|-------------------|------------------------|------------|
| 1 | QuantStats CVaR/ES API | Use `qs.stats.cvar(returns_series, confidence=0.95)` — returns a single float; import `quantstats.stats` only (avoids matplotlib surface on import); input is a daily `pd.Series` of returns | HIGH |
| 2 | Brier score for multi-class signals | Use **one-vs-rest binary Brier per direction** (BUY outcome, SELL outcome), then average; map `confidence * sign(signal)` → `confidence` on the predicted class; do NOT use multi-class Brier — too complex for 10-row training data | MEDIUM |
| 3 | IC / IC-IR methodology | Use **time-series Pearson IC** (not cross-sectional rank IC) — correlate each agent's `raw_score` with the corresponding `forward_return_5d`; require N ≥ 30 before trusting; IC-IR = `mean(IC_window) / std(IC_window)` with a 60-observation rolling window | MEDIUM |
| 4 | Walk-forward under data scarcity | **Use backtest-generated signals** (Option 1): run `Backtester` on 2020–2025 OHLCV (already in `price_history_cache` for AAPL, extendable) with `backtest_mode=True`, store results in a `backtest_signal_history` table with `source='backtest'`; use **30-day train / 10-day OOS** windows with 1 purge day; mark as "preliminary calibration" in API response | HIGH |
| 5 | Transaction cost model | Flat **10 bps (0.10%) per side** for equities (AAPL, NVDA, MSFT etc.) and **25 bps per side** for crypto (BTC, ETH); `cost_per_trade` parameter applied as `pnl_after_costs = pnl - (entry_value * cost_per_trade) - (exit_value * cost_per_trade)`; freqtrade default is `0.001` (10 bps) per side | HIGH |
| 6 | Portfolio-level VaR | Use **parametric portfolio VaR from portfolio return series** (simplest; reuses existing `portfolio_snapshots`); add covariance-aware enhancement via position-weighted returns matrix only when ≥ 2 positions have 60+ days of shared history | HIGH |
| 7 | Plan structure | **3 plans** — Plan A: standalone analytics (`engine/analytics.py` — SIG-01 + SIG-06), Plan B: tracker extensions (`tracking/tracker.py` + weight adapter — SIG-02 + SIG-03), Plan C: backtester upgrades (`backtesting/` — SIG-04 + SIG-05 + new `walk_forward.py`) | HIGH |
| 8 | Anti-patterns | Look-ahead in walk-forward (purge gap required), IC with N < 30 (suppress output not zero-fill), IC computed on aggregated signal not per-agent raw_score (wrong signal surface), survivorship bias in backtest-generated signals (document, don't fix), Brier on HOLD signals (exclude HOLD from Brier — no directional outcome to score) | HIGH |
| 9 | Testing strategy | Use **fixed synthetic returns fixture** (deterministic seed): 252-day series of synthetic agent scores + synthetic forward returns, known Pearson correlation ~0.15; test IC/ICIR against expected value within tolerance; Brier tests use manually constructed signal history rows in isolated SQLite | HIGH |
| 10 | API + frontend surfaces | Add **`GET /api/v1/analytics/risk`** (extends existing `api/routes/risk.py` or `analytics.py` — adds `cvar_95`, `es_95`, `portfolio_var` fields) and **`GET /api/v1/analytics/calibration`** (new route — returns `{agent_name: {brier_score, ic_rolling, ic_ir, sample_size}}`) | HIGH |

---

## Project Constraints (from CLAUDE.md)

- Python 3.11+ backend — all new code must run on 3.11+
- `stdlib logging` module only — no `structlog`, `loguru`, or third-party logging
- No paid data providers — all signals generated from free sources (yfinance, FRED, CCXT)
- Test discipline: 889-test floor — every deliverable ships with tests
- SQLite only — no Postgres this milestone
- `from __future__ import annotations` at top of every module
- Type hints required on all parameters and returns
- Async/await throughout (no blocking I/O on the async event loop)
- `arch>=6.0` already installed (Phase 1); `pyarrow>=14.0` already installed
- `backtest_mode=True` must be set on all `AgentInput` objects inside historical replay loops (Phase 1 contract)

---

## Critical Live Finding: signal_history Has Only 10 Rows

**Confirmed by direct DB query 2026-04-21:**
```
signal_history: count=10, min=2026-03-15 02:14:10, max=2026-03-15 20:13:18
```

All 10 rows are from a **single day** (2026-03-15). The tickers covered: AAPL, BTC-USD, GS (and 7 others from the same session). There is no multi-day history, no forward returns resolvable, and no outcome column populated (all `outcome` values are NULL).

**This rules out:**
- Standard qlib walk-forward (252-day train + 63-day OOS) — no live data
- Computing IC from live `signal_history` — no forward returns
- Computing Brier scores from live `signal_history` — no resolved outcomes

**The correct approach:** Generate a synthetic historical signal corpus via the backtester (Option 1 from the research brief), then use that corpus for initial IC/Brier calibration. See SIG-05 section for full design.

**Parquet / price cache inventory (confirmed):**
```
price_history_cache: AAPL only, 959 rows, 2022-03-07 to 2025-12-30
```
This gives 3+ years of daily OHLCV for AAPL — sufficient for walk-forward with 30-day/10-day windows (approximately 80+ windows over 3 years). Other tickers (NVDA, MSFT, BTC-USD, ETH-USD, GS) must be pre-fetched before walk-forward can run on them.

---

## Standard Stack

### Core (new additions for Phase 2)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `quantstats` | 0.0.81 | CVaR, Expected Shortfall, VaR, Sharpe, Sortino | Current latest on PyPI; actively maintained (Jan 2026 release); replaces deprecated pyfolio; MIT license |
| `scipy` | 1.15.3 | `pearsonr`, `spearmanr` for IC computation | Already installed; no new dependency; scipy 1.15.x is stable |
| `numpy` | 2.2.6 | Matrix operations for covariance VaR | Already installed |

**Installation (new only):**
```bash
pip install "quantstats>=0.0.81"
```

Add to `pyproject.toml`:
```toml
quantstats>=0.0.81
```

### Already Present (Phase 1)
| Library | Version | Notes |
|---------|---------|-------|
| `arch` | 8.0.0 | Installed Phase 1; `optimal_block_length` already in use |
| `aiosqlite` | existing | Database access (async) |
| `pandas` | 3.0.1 | Returns series manipulation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `quantstats` | `pyfolio` | pyfolio is deprecated (last commit 2022); quantstats is its maintained successor |
| `quantstats` | Custom parametric CVaR | `engine/analytics.py` already has a hand-rolled parametric CVaR (Gaussian approximation); QuantStats replaces with a verified historical-simulation implementation |
| Pearson IC | Spearman rank IC | Rank IC is more robust to outliers and is the qlib standard; however, Pearson is defensible for our 6-ticker time-series case where the signals are already on a continuous scale |

### QuantStats Import Note (CRITICAL)
[VERIFIED: direct source inspection] `quantstats` imports matplotlib at the package level in some sub-modules. To avoid importing the plotting surface in a headless server context:

```python
# Safe import — stats module only, no matplotlib surface triggered
import quantstats.stats as qs_stats

# Usage:
cvar_95 = float(qs_stats.cvar(returns_series, confidence=0.95))
var_95 = float(qs_stats.value_at_risk(returns_series, confidence=0.95))
```

Do NOT `import quantstats as qs` and call `qs.extend_pandas()` on the server path — this triggers Seaborn/Matplotlib imports.

---

## Research Q1: QuantStats CVaR/ES (SIG-01)

### Current State
`engine/analytics.py::get_portfolio_risk()` already computes a hand-rolled parametric CVaR using a Gaussian approximation:
```python
# Lines 519-523 (current implementation)
Z_95 = 1.6449
var_95 = -(mean_ret - Z_95 * daily_vol)
PHI_Z95 = 0.10313
cvar_95 = -(mean_ret - daily_vol * PHI_Z95 / 0.05)
```
This is a **normal-distribution assumption** CVaR. It understates tail risk when actual returns are fat-tailed (which is always true for equity portfolios).

### Recommendation
Replace the Gaussian CVaR approximation with QuantStats historical-simulation CVaR. QuantStats `cvar()` computes the expected value of returns below the VaR threshold — no distribution assumption.

**Integration surface:** `engine/analytics.py::get_portfolio_risk()`

**Exact API:**
```python
# [VERIFIED: quantstats 0.0.81 source, fetched 2026-04-21]
import quantstats.stats as qs_stats
import pandas as pd

def compute_cvar_es(daily_returns: list[float], confidence: float = 0.95) -> dict:
    """Compute CVaR and VaR using QuantStats historical simulation.
    
    Args:
        daily_returns: List of daily portfolio return floats (not percentages).
        confidence: Confidence level (0.95 = 95%, default).
    
    Returns:
        dict with cvar_95 and var_95 (both as positive percentage values).
    """
    if len(daily_returns) < 10:
        return {"cvar_95": None, "var_95": None}
    
    returns_series = pd.Series(daily_returns)
    
    # QuantStats returns negative floats (losses are negative)
    # We negate to express as positive loss percentages
    cvar = float(qs_stats.cvar(returns_series, confidence=confidence))
    var = float(qs_stats.value_at_risk(returns_series, confidence=confidence))
    
    return {
        "cvar_95": round(-cvar * 100, 4),   # convert to positive pct
        "var_95": round(-var * 100, 4),
    }
```

**Frequency assumption:** QuantStats assumes the returns series matches the period you pass. Daily returns series → daily VaR. Annualised VaR not needed for dashboard display.

**Short history handling:** QuantStats `cvar()` with N < 10 observations will produce unreliable values. Guard with a minimum N check. The current `get_portfolio_risk()` already has a `if len(values) < 2: return _ZERO` guard — extend to N ≥ 10 for CVaR specifically.

**Standard confidence levels:** 95% (regulatory standard, QuantStats default) and 99% (for internal risk committee use). Surface both in the API response: `cvar_95` and `cvar_99`.

**Dependency on API:** This feeds `GET /api/v1/analytics/risk` (extend existing `api/routes/risk.py` response model to include `cvar_95`, `cvar_99`, `var_95`, `portfolio_var`).

**Test approach:** Create a known returns series (e.g., `[-0.05] * 5 + [0.01] * 95`) where the CVaR is computable by hand; assert `abs(computed - expected) < 0.001`.

---

## Research Q2: Brier Score for Multi-Class Signals (SIG-02)

### The Multi-Class Problem
Our agents return `Signal.BUY / Signal.HOLD / Signal.SELL` with a `confidence` float (0–100, stored as integer in `final_confidence`). Classical Brier score is defined for binary probabilistic forecasts:

```
Brier = (1/N) * Σ (f_t - o_t)²
```

where `f_t` is predicted probability and `o_t` is binary outcome {0, 1}.

The multi-class Brier generalization (Brier 1950) is:
```
MulticlassBrier = (1/R) * Σ_r (f_{t,r} - o_{t,r})²
```
summed over R classes, but this requires class-probability vectors, which our agents do not produce (they produce a point estimate signal + scalar confidence).

### Recommended Formulation: One-vs-Rest Binary Brier

**Formulation:** For each directional signal (BUY or SELL), treat confidence as the probability of a correct directional outcome:

```python
# For a BUY signal with confidence=0.75:
#   predicted_prob = 0.75
#   outcome = 1 if forward_return_5d > 0 else 0
#   brier_contribution = (0.75 - 1)^2 = 0.0625  (if correct)
#
# For a SELL signal with confidence=0.75:
#   predicted_prob = 0.75
#   outcome = 1 if forward_return_5d < 0 else 0
#   brier_contribution = (0.75 - 1)^2 = 0.0625  (if correct)
```

**HOLD signals:** Exclude HOLD from Brier calculation. HOLD is a deliberate abstention — it does not have a directional prediction that can be scored against a binary outcome. The agent is saying "I have no directional edge". Penalising HOLDs would reward agents that never abstain even when uncertain.

**Storage:** Store `brier_score` per agent in the existing `signal_history` table or in a new `agent_calibration` table. Recommend a new table to avoid schema changes to the hot-write `signal_history` path.

**Reference:** [CITED: sklearn docs brier_score_loss] `sklearn.metrics.brier_score_loss` computes binary Brier; our formulation matches it for the one-vs-rest case. The function signature is `brier_score_loss(y_true, y_prob)` where `y_true` is binary.

**Minimum sample size:** Brier score with N < 20 directional signals per agent is unreliable. Return `None` (not 0.0) when N < 20 — this prevents the weight adapter from zeroing out an agent that simply hasn't accumulated enough data yet.

**Integration surface:** `tracking/tracker.py` — add `compute_brier_score(agent_name, horizon_days=5)` method.

**Reference implementation:**
```python
# tracking/tracker.py (new method on SignalTracker)
# [ASSUMED: sklearn available; verify before planning]
async def compute_brier_score(
    self,
    agent_name: str,
    horizon_days: int = 5,
    min_samples: int = 20,
) -> float | None:
    """One-vs-rest binary Brier score for directional signals only.
    
    Returns None if fewer than min_samples resolved directional signals exist.
    Lower is better (0.0 = perfect, 0.25 = random, 1.0 = perfectly wrong).
    """
    rows = await self._store.get_agent_directional_signals_with_outcomes(
        agent_name, horizon_days
    )
    # Filter to BUY / SELL only (exclude HOLD)
    directional = [r for r in rows if r["signal"] in ("BUY", "SELL")]
    if len(directional) < min_samples:
        return None
    
    squared_errors = []
    for r in directional:
        prob = r["confidence"] / 100.0  # normalize 0–100 → 0–1
        if r["signal"] == "BUY":
            outcome = 1.0 if r["forward_return"] > 0 else 0.0
        else:  # SELL
            outcome = 1.0 if r["forward_return"] < 0 else 0.0
        squared_errors.append((prob - outcome) ** 2)
    
    return round(sum(squared_errors) / len(squared_errors), 4)
```

**Data requirement:** This method needs `forward_return_5d` for each historical signal. The `signal_history` table has `outcome_return_pct` and `outcome_resolved_at` columns — these are already defined in the schema but currently NULL. The daemon's weekly revaluation job (`daemon/jobs.py::run_weekly_revaluation`) should populate these.

**Schema gap:** `signal_history` does NOT have a per-agent signal row — it stores the aggregated signal plus `agent_signals_json`. To compute per-agent Brier, you must parse `agent_signals_json`. This is acceptable for low-frequency batch computation (daily daemon job), not hot-path per-request computation.

---

## Research Q3: IC / IC-IR Methodology (SIG-03)

### Cross-Sectional vs. Time-Series IC
**qlib standard (cross-sectional):** IC = Spearman correlation of factor scores across N tickers on day T with their forward returns on day T+k. This requires a universe of N tickers analyzed simultaneously.

**Our situation:** We run analysis per-ticker asynchronously. We don't always have the same set of tickers analyzed on the same day. This makes cross-sectional IC impractical.

**Recommended approach: Time-series Pearson IC** per agent.
- For agent A, collect the time-series of `(raw_score_t, forward_return_{t+5d})` pairs across all tickers and dates
- IC = Pearson correlation(raw_score_t, forward_return_{t+5d})
- ICIR = mean(IC over rolling 60-day window) / std(IC over rolling 60-day window)

This is the approach recommended in the STACK.md research and is appropriate for our architecture.

### Forward Return Horizon
Use **5 trading days (1 week)** as the primary horizon. Rationale:
- Our agents run on daily cadence
- 5-day horizon is long enough for signals to manifest but short enough to accumulate observations quickly
- Secondary horizon: 21-day (1 month) for longer-term IC — label as `ic_21d`

### Minimum Sample Size
Rule of thumb from IC literature [CITED: mrzepczynski.blogspot.com 2024]: IC estimates from N < 30 observations have standard error > 0.18 (high noise). At N = 30, a true IC of 0.05 is indistinguishable from 0 at 95% confidence. At N = 100, the SE drops to 0.10.

**Decision:** Return `ic=None` when N < 30 observations for the agent-ticker combination. Do not zero-fill — None signals "insufficient data" to the weight adapter, which should then fall back to default weights for that agent.

### IC-IR Computation
```python
# [ASSUMED: scipy.stats.pearsonr already available]
from scipy.stats import pearsonr

def compute_rolling_ic(
    scores: list[float],        # agent raw_score series
    forward_returns: list[float],  # corresponding forward_return_5d
    window: int = 60,
) -> list[float | None]:
    """Rolling Pearson IC over a sliding window.
    
    Returns None at positions with insufficient data.
    """
    n = len(scores)
    ics = []
    for i in range(n):
        if i < window - 1:
            ics.append(None)
            continue
        s_window = scores[i - window + 1 : i + 1]
        r_window = forward_returns[i - window + 1 : i + 1]
        valid = [(s, r) for s, r in zip(s_window, r_window) if s is not None and r is not None]
        if len(valid) < 30:  # minimum N enforcement
            ics.append(None)
            continue
        s_vals, r_vals = zip(*valid)
        ic, _ = pearsonr(s_vals, r_vals)
        ics.append(ic)
    return ics

def compute_icir(rolling_ics: list[float | None]) -> float | None:
    """IC Information Ratio = mean(IC) / std(IC)."""
    valid = [ic for ic in rolling_ics if ic is not None]
    if len(valid) < 5:  # need at least 5 IC values to estimate ICIR
        return None
    import statistics
    mean_ic = statistics.mean(valid)
    std_ic = statistics.stdev(valid)
    if std_ic == 0:
        return None
    return round(mean_ic / std_ic, 4)
```

### Integration with Weight Adapter
The `engine/weight_adapter.py` currently uses EWMA accuracy (hit rate) to set weights. The IC path should be additive, not replacing:

```python
# engine/weight_adapter.py — new method
async def compute_ic_weights(
    self,
    asset_type: str = "stock",
    window: int = 60,
) -> dict[str, float] | None:
    """Compute weights from per-agent IC. Returns None if insufficient data.
    
    IC-based weights: weight_i = max(0, IC_i) / sum(max(0, IC_j) for all j)
    Agents with negative IC get weight 0 (not negative weight).
    Falls back to None → caller uses existing EWMA accuracy weights.
    """
    ...
```

**Integration surface:** `tracking/tracker.py` (IC computation) + `engine/weight_adapter.py` (IC → weight conversion).

**Phasing:** IC computation should run in the weekly revaluation daemon job, not per-request. Store computed IC in `portfolio_meta` table (already used for `adaptive_weights`).

---

## Research Q4: Walk-Forward Window Sizing Under Data Scarcity (SIG-05)

### Situation Assessment (CONFIRMED by live DB query)

| Fact | Value |
|------|-------|
| Live `signal_history` rows | 10 (single day: 2026-03-15) |
| Live `outcome` populated | 0 rows (all NULL) |
| `price_history_cache` AAPL | 959 rows, 2022-03-07 to 2025-12-30 |
| Other tickers in cache | None (only AAPL) |
| Standard qlib windows | 252-day train + 63-day OOS = requires 315+ days minimum |

### Selected Approach: Option 1 — Backtest-Generated Signals

Run `backtesting/engine.py::Backtester` over historical OHLCV (2022–2025) with `backtest_mode=True`, capture the per-date `agent_signals_log` entries, compute forward returns for each signal date, and store the result in a `backtest_signal_history` table. This corpus then feeds IC/Brier computation.

**Why Option 1 over the alternatives:**
- Option 2 (defer until live history accumulates) blocks SIG-03/IC-ICIR indefinitely — months of dead time
- Option 3 (live 30/10 windows on 10 rows) is statistically meaningless — 10 rows cannot train any model

**Architecture of `backtesting/walk_forward.py` (new file):**

```python
# backtesting/walk_forward.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta  # [ASSUMED: python-dateutil installed]
import pandas as pd

@dataclass
class WalkForwardWindow:
    train_start: date
    train_end: date
    oos_start: date
    oos_end: date
    window_idx: int

@dataclass
class WalkForwardResult:
    windows: list[WalkForwardWindow]
    per_window_metrics: list[dict]  # {window_idx, sharpe, total_return, n_trades}
    overall_ic: float | None
    overall_icir: float | None
    warnings: list[str]
    source: str  # "backtest" | "live"

def generate_walk_forward_windows(
    start: date,
    end: date,
    train_days: int = 30,
    oos_days: int = 10,
    step_days: int = 10,
    purge_days: int = 1,
) -> list[WalkForwardWindow]:
    """Generate rolling train/OOS windows with purge gap.
    
    purge_days: gap between train_end and oos_start to prevent label leakage.
    For daily signals with 5-day forward returns, purge ≥ 5 days is ideal;
    purge=1 is the minimum viable (removes the single overlap point).
    """
    windows = []
    idx = 0
    train_start = start
    while True:
        train_end = train_start + timedelta(days=train_days - 1)
        oos_start = train_end + timedelta(days=purge_days + 1)
        oos_end = oos_start + timedelta(days=oos_days - 1)
        if oos_end > end:
            break
        windows.append(WalkForwardWindow(
            train_start=train_start,
            train_end=train_end,
            oos_start=oos_start,
            oos_end=oos_end,
            window_idx=idx,
        ))
        train_start += timedelta(days=step_days)
        idx += 1
    return windows
```

### Defensible Window Sizes for Preliminary Calibration

Given AAPL OHLCV from 2022-03-07 to 2025-12-30 (≈3.8 years = ≈950 trading days):

| Window Config | Train Days | OOS Days | Purge | Approx Windows (3yr) | IC est. quality |
|---------------|-----------|---------|-------|---------------------|-----------------|
| **Recommended (v1)** | **30** | **10** | **1** | **≈80** | Low (N=30, SE≈0.18) |
| Standard | 252 | 63 | 5 | ≈4 | Would-be-reliable |
| Intermediate | 90 | 21 | 5 | ≈13 | Marginal |

Use the 30/10 config and mark all outputs with `"preliminary_calibration": true` in the API response and in DB metadata. This is not evasion — it's accurate characterisation.

### Overlap and Label Leakage Prevention
**Critical issue:** Our backtester uses TechnicalAgent which computes SMA200 (200-day lookback). A 30-day training window whose signals are derived from price data that overlaps with the OOS price data creates leakage through the indicator calculations.

**Mitigation:** 
1. The purge gap (1 day minimum) prevents the last training-window signal from being in the OOS period
2. For the 5-day forward return horizon, the purge should ideally be 5 days. Use `purge_days=5` when walk-forward is used for IC computation; `purge_days=1` when used only for Sharpe comparison
3. Document in the API response: `"note": "SMA200 uses up to 200 days of lookback; signals in early training windows may have full-history advantage"`

### Purged K-Fold / Embargo
**Decision: Do NOT implement full CPCV (Combinatorial Purged Cross-Validation, Lopez de Prado).** It requires `mlfinlab` (MEDIUM confidence, niche library) and adds substantial complexity for minimal benefit at this data scale. The simple purge gap is sufficient for Phase 2.

**Label leakage risk assessment:** Our signals are TechnicalAgent-only in backtest mode. Technical indicators are derived from price history only, with no forward information. The leakage risk is LOW compared to ML-based systems where features and labels share the same period. Document this in the walk-forward result warnings.

### `backtest_signal_history` Table Schema

```sql
CREATE TABLE IF NOT EXISTS backtest_signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    signal_date TEXT NOT NULL,          -- ISO date of signal generation
    agent_name TEXT NOT NULL,
    raw_score REAL,                     -- agent's raw signal score (backtested)
    signal TEXT NOT NULL,               -- BUY/HOLD/SELL
    confidence REAL,
    forward_return_5d REAL,            -- realized return 5 days after signal_date
    forward_return_21d REAL,           -- realized return 21 days after signal_date
    source TEXT DEFAULT 'backtest',    -- 'backtest' | 'live'
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_bsh_ticker_date ON backtest_signal_history(ticker, signal_date);
CREATE INDEX IF NOT EXISTS idx_bsh_agent_date ON backtest_signal_history(agent_name, signal_date);
```

**Pre-populate workflow (in `backtesting/walk_forward.py`):**
1. For each ticker with ≥ 60 days of OHLCV in `price_history_cache`, run `Backtester` with `backtest_mode=True`
2. From `agent_signals_log`, compute `forward_return_5d` by looking up the price 5 trading days later in the OHLCV data
3. INSERT into `backtest_signal_history`
4. Flag in API response: `"signal_corpus_source": "backtest_generated"`

---

## Research Q5: Transaction Cost Model (SIG-04)

### Standard Market Cost Estimates

**Equities (AAPL, NVDA, MSFT, GS — large cap US):**
- Exchange commission: ~$0 (Robinhood, IBKR Lite) to ~1 bps (IBKR Pro)
- Bid-ask spread (effective half-spread): 1–3 bps for large-cap S&P 500
- Market impact (realistic for retail size): negligible
- **Total round-trip cost: 2–6 bps (1–3 bps per side)**

**Crypto (BTC-USD, ETH-USD on Coinbase/Binance):**
- Taker fee: 5–25 bps per side (Coinbase Pro: 60 bps for <$10k/mo; Binance: 10 bps; Coinbase Advanced: 60 bps)
- Bid-ask spread: 1–5 bps on liquid pairs
- **Total round-trip cost: 20–70 bps (10–35 bps per side)**

**Freqtrade default** [VERIFIED: freqtrade.io/en/stable/configuration/ 2026-04-21]: `fee=0.001` (10 bps per side), applied twice per trade (entry + exit = 20 bps round-trip total). This is their conservative but realistic default for liquid crypto pairs.

### Recommended Defaults

```python
# backtesting/models.py — add to BacktestConfig
COST_PER_TRADE_EQUITY: float = 0.001   # 10 bps per side (entry + exit = 20 bps RT)
COST_PER_TRADE_CRYPTO: float = 0.0025  # 25 bps per side (entry + exit = 50 bps RT)

@dataclass
class BacktestConfig:
    ...
    cost_per_trade: float | None = None  # None → use asset-type default
```

### P&L Application Formula

Apply costs at both entry and exit:

```python
# backtesting/engine.py — trade execution
def _apply_costs(trade_value: float, cost_per_trade: float) -> float:
    """Deduct transaction cost from trade value."""
    return trade_value * cost_per_trade

# On entry (BUY):
entry_cost = trade_value * cost_per_trade
cash -= (trade_value + entry_cost)  # pay for shares + cost

# On exit (SELL):
exit_value = shares * exit_price
exit_cost = exit_value * cost_per_trade
cash += (exit_value - exit_cost)     # receive proceeds - cost

# Net P&L impact per round-trip:
# pnl_with_costs = (exit_price - entry_price) * shares - entry_cost - exit_cost
```

### Phase 4 Dependency
Transaction costs feed directly into TTWROR accuracy in Phase 4. The `BacktestResult.metrics` must include:
- `total_costs_paid`: sum of all transaction costs across all trades
- `cost_drag_pct`: total_costs_paid / initial_capital * 100

These fields enable Phase 4's `PerformancePage.tsx` to show cost-adjusted vs. gross returns.

### Test
Verify: a backtest with `cost_per_trade=0.001` on a single round-trip trade produces `total_return` strictly lower than the same backtest with `cost_per_trade=0.0`. Assert the difference equals approximately `entry_value * 0.001 * 2`.

---

## Research Q6: Portfolio-Level VaR with Covariance (SIG-06)

### Current State
`engine/analytics.py::get_portfolio_risk()` computes parametric VaR on the portfolio-level return series (sum of portfolio snapshot `total_value` changes). This is already correlation-aware in a weak sense — it uses the realized portfolio returns, which inherently reflect cross-position correlations.

**What it misses:** Position-level VaR decomposition and forward-looking covariance VaR (useful when position weights change frequently).

### Recommended Approach: Parametric Portfolio VaR (Tier 1) + Position Covariance VaR (Tier 2)

**Tier 1 (SIG-06 minimal):** Replace the Gaussian approximation in `get_portfolio_risk()` with QuantStats historical-simulation VaR on the portfolio return series. This is already covariance-aware via the realized returns. Label this `portfolio_var` in the API response.

**Tier 2 (SIG-06 full):** Add a covariance-matrix position VaR computation when ≥ 2 positions exist with shared history:

```python
# engine/analytics.py — new method
async def get_portfolio_var_covariance(
    self,
    positions: list[dict],   # [{ticker, weight, asset_type}, ...]
    days: int = 252,
    confidence: float = 0.95,
) -> dict:
    """Portfolio VaR using position covariance matrix.
    
    Uses price_history_cache for historical returns per ticker.
    Only runs when >= 2 positions have >= 60 shared trading days.
    """
    import numpy as np
    
    # 1. Fetch per-ticker return series from price_history_cache
    # 2. Align to common dates (inner join)
    # 3. Compute covariance matrix: cov = returns_matrix.cov()
    # 4. Portfolio variance: w.T @ cov @ w  (w = weight vector)
    # 5. Portfolio VaR: portfolio_std * z_score * sqrt(1)
    #    where z_score = scipy.stats.norm.ppf(confidence)
    
    # Returns: {portfolio_var_95, component_var: {ticker: var}, diversification_benefit}
```

**Key insight on simplicity:** For a daily-cadence signal tool with 5 positions, the portfolio return series VaR (Tier 1) is already sufficient for the `portfolio_var` field required by SIG-06. The covariance VaR (Tier 2) adds meaningful value only when positions are large relative to each other and their correlations are high — which may not be the typical use case. Implement Tier 2 only if Tier 1 is done first.

**Integration surface:** `engine/analytics.py` (both tiers). API route: extend `GET /api/v1/analytics/risk` response model.

---

## Research Q7: Integration Surfaces and Dependency Ordering

### Within-Phase Dependencies

```
SIG-01 (CVaR)          ←── standalone, engine/analytics.py
SIG-06 (portfolio VaR) ←── standalone but shares analytics.py with SIG-01
SIG-04 (tx costs)      ←── standalone, backtesting/engine.py
SIG-02 (Brier)         ←── depends on signal_history having outcomes
                           → BLOCKED on live data; use backtest_signal_history for initial calibration
SIG-03 (IC/ICIR)       ←── depends on SIG-02's signal corpus + feeds weight_adapter.py
SIG-05 (walk-forward)  ←── depends on SIG-04 for realistic OOS P&L
                       ←── generates the signal corpus that SIG-02 and SIG-03 need
                       ←── creates backtest_signal_history (new table)
```

**Correct build order:**
1. SIG-04 (transaction costs) — no dependencies, unblocks SIG-05
2. SIG-01 + SIG-06 (CVaR + portfolio VaR) — parallel, no dependencies
3. SIG-05 (walk-forward scaffold + backtest_signal_history generation) — depends on SIG-04
4. SIG-02 + SIG-03 (Brier + IC) — depends on SIG-05's signal corpus

### API Route Design

**`GET /api/v1/analytics/risk`** (extend existing `api/routes/risk.py` or `api/routes/analytics.py`):
```json
{
  "cvar_95": 2.15,
  "cvar_99": 3.40,
  "var_95": 1.68,
  "portfolio_var": 1.72,
  "portfolio_var_source": "historical_simulation",
  "data_points": 87,
  "period_days": 90
}
```

**`GET /api/v1/analytics/calibration`** (new route in `api/routes/analytics.py` or new `api/routes/calibration.py`):
```json
{
  "agents": {
    "TechnicalAgent": {
      "brier_score": 0.18,
      "ic_rolling_5d": 0.06,
      "ic_ir": 0.42,
      "sample_size": 156,
      "preliminary_calibration": true,
      "signal_source": "backtest_generated"
    },
    "FundamentalAgent": {
      "brier_score": null,
      "ic_rolling_5d": null,
      "ic_ir": null,
      "sample_size": 0,
      "note": "FundamentalAgent excluded from backtest-generated signals (non-PIT)"
    }
  },
  "corpus_coverage": {
    "date_range": ["2022-03-07", "2025-12-30"],
    "tickers": ["AAPL"],
    "total_signal_observations": 956
  }
}
```

**Note on `FundamentalAgent` in calibration:** `FundamentalAgent` returns HOLD in `backtest_mode=True` (Phase 1 contract). It will have no valid directional signals in the backtest corpus. Its IC/Brier will be NULL. This is correct — we cannot calibrate it without point-in-time data. Document this clearly in the API response.

### Phase 4 Dependency
Phase 4's TTWROR calculation depends on transaction costs being correctly applied in `BacktestResult`. Ensure `BacktestResult.metrics` includes `total_costs_paid` and `n_trades` from Phase 2's SIG-04 work before Phase 4 planning begins.

---

## Research Q8: Anti-Pattern Catalog

### AP-01: Look-Ahead Bias in Walk-Forward Windows
**What happens:** Technical indicators (SMA200) computed at a signal date T use up to 200 days of prior price data. If the training window is only 30 days but the indicator has 200-day memory, the signal at day 30 of the training window uses price data from 170 days before the window started. This is fine (no future data) — the look-ahead risk is different: the forward return used as the IC label must be computed AFTER the signal date, not on the same day.
**Prevention:** Always compute `forward_return_5d` for signal at date T using the price at date T+5, never T. In `backtesting/walk_forward.py`, fetch the price 5 trading days after each signal date from the OHLCV DataFrame; do not use any data from within the signal date's row.

### AP-02: IC Computed on Aggregated Signal (not per-agent raw_score)
**What happens:** Using `final_signal` (BUY/HOLD/SELL) or `raw_score` from the aggregated `AggregatedSignal` to compute IC conflates the signal from all agents. This measures the aggregator's quality, not individual agent quality. IC/Brier must be computed from `agent_signals_json` per agent.
**Prevention:** Parse `agent_signals_json` in `tracking/tracker.py` to extract each agent's `signal` and `confidence` separately. Use the per-agent `raw_score` or `confidence * sign(signal)` — whichever is more directly interpretable as a continuous score — as the IC input.

### AP-03: IC with N < 30 Zero-Filled Instead of NULL
**What happens:** If N = 10 and IC is computed and stored as 0.08, the weight adapter treats this as a valid IC estimate and adjusts weights. With SE ≈ 0.18 at N=10, the IC estimate is pure noise.
**Prevention:** Return `ic=None` for N < 30. In the weight adapter, treat `None` as "revert to default weight for this agent". Never substitute 0.0 for None in IC fields.

### AP-04: Survivorship Bias in Backtest Signal Corpus
**What happens:** The `price_history_cache` contains only currently-listed tickers (yfinance limitation). A ticker delisted between 2022 and 2025 will not appear. The IC/Brier corpus systematically excludes failure cases.
**Prevention:** Document this in the `backtest_signal_history` metadata and in `GET /api/v1/analytics/calibration` response. Flag: `"survivorship_bias_warning": "Corpus contains only currently-listed tickers. IC/Brier estimates may be optimistic."`. Do not attempt to fix this in Phase 2.

### AP-05: Brier Score Applied to HOLD Signals
**What happens:** Including HOLD signals in Brier calculation without a clear directional outcome to score against. A HOLD on a day when the price rose 2% is not a "wrong" call — the agent may have been deliberately abstaining.
**Prevention:** Exclude HOLD from Brier. Only BUY and SELL signals have directional predictions that can be evaluated.

### AP-06: Transaction Costs Applied Only at Entry, Not Exit
**What happens:** Some naive implementations apply `cost_per_trade` only at entry (BUY cost). The exit (SELL) also incurs spread and commission. Single-sided costs understate total drag by 50%.
**Prevention:** Apply `cost_per_trade` at both entry (when cash is spent) and exit (when proceeds are received). Total round-trip cost = `trade_value * cost_per_trade * 2`.

### AP-07: QuantStats `extend_pandas()` in Server Code
**What happens:** `qs.extend_pandas()` patches `pd.Series` to add QuantStats methods globally. It also imports Seaborn and Matplotlib as side effects. In a headless FastAPI process, this can fail or add unnecessary import overhead.
**Prevention:** Use `import quantstats.stats as qs_stats` and call `qs_stats.cvar()` directly. Never call `qs.extend_pandas()` in API or daemon code.

### AP-08: CVaR Reported as Negative (Loss Sign Convention)
**What happens:** QuantStats `cvar()` returns a negative float (loss). If surfaced directly to the API, consumers see `-2.15` and must know to negate it. The existing `get_portfolio_risk()` already uses a positive convention for `cvar_95`.
**Prevention:** Negate the QuantStats output: `cvar_95 = round(-qs_stats.cvar(series), 4)`. Keep the sign convention consistent with existing `var_95` and `cvar_95` fields in the current response model.

---

## Research Q9: Testing Strategy

### The Core Problem
We cannot write integration tests that call live yfinance for IC/Brier — too slow, non-deterministic, network-dependent. We need deterministic signal fixtures.

### Recommended Test Architecture

**Fixture: synthetic_signal_corpus**
```python
# tests/fixtures/synthetic_signal_corpus.py
import numpy as np
import pandas as pd

def make_synthetic_signal_corpus(
    n_days: int = 100,
    n_tickers: int = 3,
    true_ic: float = 0.12,   # known Pearson correlation between score and return
    seed: int = 42,
) -> list[dict]:
    """Generate a synthetic signal corpus with known IC.
    
    Returns list of dicts matching backtest_signal_history schema.
    IC between raw_score and forward_return_5d is approximately true_ic.
    """
    rng = np.random.default_rng(seed)
    tickers = ["SYN-A", "SYN-B", "SYN-C"][:n_tickers]
    rows = []
    for ticker in tickers:
        scores = rng.normal(0, 1, n_days)  # agent raw scores
        noise = rng.normal(0, 1, n_days)
        # Forward returns = true_ic * score + noise component
        returns = true_ic * scores + np.sqrt(1 - true_ic**2) * noise
        for i in range(n_days):
            signal = "BUY" if scores[i] > 0 else ("SELL" if scores[i] < -0.5 else "HOLD")
            rows.append({
                "ticker": ticker,
                "agent_name": "TechnicalAgent",
                "raw_score": float(scores[i]),
                "signal": signal,
                "confidence": min(95, 50 + abs(scores[i]) * 20),
                "forward_return_5d": float(returns[i]),
                "signal_date": f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                "source": "synthetic",
            })
    return rows
```

**IC test:**
```python
# tests/test_signal_quality_02_ic_brier.py
def test_ic_matches_known_correlation():
    corpus = make_synthetic_signal_corpus(n_days=100, true_ic=0.12, seed=42)
    scores = [r["raw_score"] for r in corpus if r["ticker"] == "SYN-A"]
    returns = [r["forward_return_5d"] for r in corpus if r["ticker"] == "SYN-A"]
    ic = compute_pearson_ic(scores, returns)
    # IC should be within ±0.05 of true_ic with seed=42
    assert abs(ic - 0.12) < 0.05, f"IC {ic} far from expected 0.12"
```

**Brier test:**
```python
def test_brier_score_perfect_predictor():
    # Perfect predictor: confidence=95% always, always correct
    signals = [
        {"signal": "BUY", "confidence": 95.0, "forward_return": 0.01}
        for _ in range(30)
    ]
    bs = compute_brier_score_from_rows(signals)
    assert bs < 0.05, f"Expected near-0 Brier, got {bs}"

def test_brier_score_random_predictor():
    # Random predictor: confidence=50%, equally right and wrong
    rng = np.random.default_rng(0)
    signals = [
        {"signal": "BUY", "confidence": 50.0,
         "forward_return": 0.01 if rng.random() > 0.5 else -0.01}
        for _ in range(100)
    ]
    bs = compute_brier_score_from_rows(signals)
    # Random predictor Brier ≈ 0.25 (binary, 50% confidence, 50/50 outcomes)
    assert abs(bs - 0.25) < 0.05
```

**Walk-forward test (no network required):**
```python
def test_walk_forward_window_generation():
    windows = generate_walk_forward_windows(
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        train_days=30, oos_days=10, step_days=10, purge_days=1,
    )
    assert len(windows) > 20, "Should generate many windows over 1 year"
    for w in windows:
        assert w.oos_start > w.train_end, "OOS must start after train"
        assert (w.oos_start - w.train_end).days >= 1, "Purge gap must be >= 1"
```

**CVaR test:**
```python
def test_cvar_replaces_gaussian_approximation():
    # Returns series where Gaussian CVaR would understate (fat tails)
    returns = [-0.10, -0.09, -0.08] + [0.005] * 97  # fat left tail
    result = compute_cvar_es(returns)
    # QuantStats historical CVaR should be around 9-10% (not Gaussian 2%)
    assert result["cvar_95"] > 5.0, f"CVaR {result['cvar_95']} seems too low for fat-tail series"
```

---

## Research Q10: API + Frontend Surfaces

### Minimum Phase 2 API Surface (Phase 4-consumable)

**Existing route to extend:** Check `api/routes/risk.py` (confirmed in STRUCTURE.md) — this is the most natural home for SIG-01/06 outputs.

**New route needed:** `GET /api/v1/analytics/calibration` (new file `api/routes/calibration.py` or extend `api/routes/analytics.py`).

### Response Contracts

`GET /api/v1/analytics/risk` extension:
```json
{
  "existing_fields": "...",
  "cvar_95": 2.15,
  "cvar_99": 3.40,
  "var_95": 1.68,
  "portfolio_var": 1.72,
  "portfolio_var_method": "historical_simulation",
  "data_points": 87
}
```

`GET /api/v1/analytics/calibration` (new):
```json
{
  "agents": {
    "TechnicalAgent": {
      "brier_score": 0.18,
      "ic_5d": 0.06,
      "ic_ir": 0.42,
      "sample_size": 156,
      "preliminary_calibration": true,
      "signal_source": "backtest_generated"
    }
  },
  "corpus_metadata": {
    "date_range": ["2022-03-07", "2025-12-30"],
    "tickers_covered": ["AAPL"],
    "total_observations": 956,
    "survivorship_bias_warning": true
  }
}
```

### Frontend Integration Points (Phase 4 hooks)
The `WeightsPage.tsx` already renders agent weights — Phase 4 can extend it to show per-agent `brier_score` and `ic_5d` alongside the existing weight sliders. No new pages required for Phase 2 — the data surfaces via API, and Phase 4 does the display work.

**Minimum backend work in Phase 2:** Both new API endpoints (risk extension + calibration) must exist before Phase 4 starts. Phase 4 should not define these APIs — Phase 2 owns them.

---

## Plan Structure Recommendation

### Recommended: 3 Plans

**Rationale:** The 6 requirements split cleanly into 3 independent work streams. Plans A and B can execute in parallel after Plan C generates the signal corpus (or Plan B uses synthetic fixtures in tests and real corpus for integration tests).

```
Plan 01: Analytics Extensions (SIG-01 + SIG-06)
  Files: engine/analytics.py, api/routes/risk.py (or analytics.py)
  Duration estimate: M (~2–3 hours)
  Dependencies: quantstats install only
  Delivers: cvar_95, cvar_99, var_95, portfolio_var in GET /api/v1/analytics/risk

Plan 02: Backtester Upgrades (SIG-04 + SIG-05)
  Files: backtesting/engine.py, backtesting/models.py, backtesting/walk_forward.py (new),
         db/database.py (backtest_signal_history table), daemon/jobs.py (pre-populate job)
  Duration estimate: L (~4–6 hours)
  Dependencies: python-dateutil (check if installed); no new libs otherwise
  Delivers: cost_per_trade, walk_forward_windows in BacktestResult, backtest_signal_history populated
  CRITICAL: Must complete before Plan 03 to provide signal corpus

Plan 03: Signal Calibration (SIG-02 + SIG-03)
  Files: tracking/tracker.py, engine/weight_adapter.py, api/routes/calibration.py (new),
         api/models.py (new response models)
  Duration estimate: M (~3–4 hours)
  Dependencies: SIG-05 corpus (backtest_signal_history populated)
  Delivers: Brier score, IC/ICIR per agent, GET /api/v1/analytics/calibration
```

**Why not 1 plan:** The 6 requirements touch 8 different files across 3 different layers. A single plan would exceed the GSD plan scope guideline and would block parallel execution.

**Why not 4+ plans:** SIG-01 and SIG-06 share `engine/analytics.py` and can be done in a single edit session. SIG-04 and SIG-05 share `backtesting/engine.py` and `BacktestConfig`/`BacktestResult` models.

**Execution order:** Plan 01 (parallel with Plan 02) → Plan 03 (after Plan 02 finishes).

---

## Library Decisions

| Library | Pin | Why This Version | Status |
|---------|-----|-----------------|--------|
| `quantstats` | `>=0.0.81` | Latest (Jan 2026); 0.0.81 confirmed on PyPI 2026-04-21 | NEEDS_INSTALL |
| `scipy` | `>=1.15.3` | Already installed at 1.15.3; `pearsonr` API stable | ALREADY_INSTALLED |
| `numpy` | `>=2.2.6` | Already installed; `cov()`, matrix multiply | ALREADY_INSTALLED |
| `arch` | `>=8.0.0` | Already installed (Phase 1); reuse for block bootstrap | ALREADY_INSTALLED |
| `python-dateutil` | check needed | `relativedelta` for walk-forward window generation; likely already installed (common transitive dep) | CHECK_FIRST |

**`python-dateutil` check:**
```bash
pip show python-dateutil
```
If not installed, replace `relativedelta` with `timedelta(days=days)` arithmetic — avoids the dependency entirely for our use case.

**Version pin for `pyproject.toml`:**
```toml
quantstats>=0.0.81
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `quantstats` | SIG-01, SIG-06 | No | — | Use existing hand-rolled Gaussian CVaR (inferior but functional) |
| `scipy` | SIG-03 (IC/Pearson) | Yes | 1.15.3 | No fallback needed |
| `numpy` | SIG-06 (covariance VaR) | Yes | 2.2.6 | No fallback needed |
| `arch` | SIG-05 (optional block bootstrap in walk-forward) | Yes | 8.0.0 | No fallback needed |
| SQLite `price_history_cache` AAPL data | SIG-05 | Yes | 959 rows, 2022–2025 | Must extend to other tickers |
| SQLite `signal_history` outcomes | SIG-02, SIG-03 | No (0 resolved rows) | — | Use `backtest_signal_history` corpus |

**Blocking items:**
- `quantstats` must be installed before Plan 01 can ship. Add to Wave 0.
- `backtest_signal_history` must be populated with at least 30+ signal rows per agent before Plan 03 can run IC/Brier. Plan 02 pre-populates this.

**Missing dependencies with no fallback:**
- None that block Phase 2 — `quantstats` has a clear install path.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.23+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_signal_quality_*.py -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| SIG-01 | `cvar_95` in GET /api/v1/analytics/risk response | integration | `pytest tests/test_signal_quality_01_cvar.py -q` | Wave 0 |
| SIG-01 | QuantStats CVaR != Gaussian CVaR on fat-tail series | unit | `pytest tests/test_signal_quality_01_cvar.py::test_cvar_not_gaussian -q` | Wave 0 |
| SIG-02 | Brier score returned for TechnicalAgent with N≥20 | unit | `pytest tests/test_signal_quality_02_ic_brier.py::test_brier_technical -q` | Wave 0 |
| SIG-02 | Brier=None for N<20 samples | unit | `pytest tests/test_signal_quality_02_ic_brier.py::test_brier_insufficient_data -q` | Wave 0 |
| SIG-03 | Rolling IC close to known synthetic IC | unit | `pytest tests/test_signal_quality_02_ic_brier.py::test_ic_matches_known_correlation -q` | Wave 0 |
| SIG-03 | IC=None for N<30 | unit | `pytest tests/test_signal_quality_02_ic_brier.py::test_ic_none_small_sample -q` | Wave 0 |
| SIG-04 | Backtest with cost_per_trade=0.001 has lower return than cost=0 | unit | `pytest tests/test_signal_quality_03_tx_costs.py::test_cost_reduces_return -q` | Wave 0 |
| SIG-04 | Equity default cost = 0.001, crypto default = 0.0025 | unit | `pytest tests/test_signal_quality_03_tx_costs.py::test_default_costs -q` | Wave 0 |
| SIG-05 | walk_forward_windows returns non-empty list for 3yr period | unit | `pytest tests/test_signal_quality_04_walk_forward.py::test_window_generation -q` | Wave 0 |
| SIG-05 | OOS start always > train end | unit | `pytest tests/test_signal_quality_04_walk_forward.py::test_no_oos_train_overlap -q` | Wave 0 |
| SIG-06 | portfolio_var in GET /api/v1/analytics/risk response | integration | `pytest tests/test_signal_quality_01_cvar.py::test_portfolio_var_present -q` | Wave 0 |

### Wave 0 Gaps
- [ ] `tests/test_signal_quality_01_cvar.py` — covers SIG-01 + SIG-06
- [ ] `tests/test_signal_quality_02_ic_brier.py` — covers SIG-02 + SIG-03
- [ ] `tests/test_signal_quality_03_tx_costs.py` — covers SIG-04
- [ ] `tests/test_signal_quality_04_walk_forward.py` — covers SIG-05
- [ ] Install quantstats: `pip install "quantstats>=0.0.81"` + add to `pyproject.toml`
- [ ] Verify `python-dateutil` installed: `pip show python-dateutil`

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `sklearn` (scikit-learn) is available in the project environment | SIG-02 Brier | Brier implementation must avoid sklearn; use pure numpy instead. Replace `brier_score_loss` with manual MSE. Low risk — can be computed without sklearn. |
| A2 | `python-dateutil` is a transitive dependency (from pandas or another lib) | SIG-05 walk-forward | `timedelta` arithmetic can replace `relativedelta` completely — zero risk to implementation |
| A3 | The `signal_history.outcome_return_pct` and `outcome_resolved_at` columns exist in the schema (visible in schema from DB query) but the daemon does NOT currently populate them | SIG-02/03 | If daemon does populate them, we should use live data sooner. Low risk — the backtest corpus is sufficient for Phase 2 regardless. |
| A4 | `api/routes/risk.py` is the canonical home for the risk endpoint (inferred from STRUCTURE.md) | Q10 API surfaces | May be in `api/routes/analytics.py` instead. Either works; the endpoint URL `GET /api/v1/analytics/risk` is the contract, not the file location. |
| A5 | Walk-forward over AAPL 2022-2025 will generate ≥80 30/10-day windows | SIG-05 | Confirmed: 3.8 years × ~26 step periods per year = ~98 windows. Slight risk if many holidays reduce trading days. Safe estimate is 70+. |

---

## Open Questions

1. **`signal_history` outcome population — daemon gap?**
   - What we know: `outcome`, `outcome_return_pct`, `outcome_resolved_at` columns exist in `signal_history` schema (confirmed via DB query), but all 10 rows have `outcome=NULL`
   - What's unclear: Is the daemon's weekly revaluation job supposed to populate these columns, and if so, is the logic already written or still a stub?
   - Recommendation: Check `daemon/jobs.py::run_weekly_revaluation()` for outcome resolution logic. If not present, add as part of SIG-02 Plan 03 work.

2. **Forward return computation for backtest signal corpus**
   - What we know: `price_history_cache` has AAPL OHLCV to 2025-12-30. To compute `forward_return_5d` for a signal on date T, we need the close price at T+5 trading days.
   - What's unclear: `pd.bdate_range` gives business days but doesn't account for market holidays (yfinance uses actual trading days). Off-by-one in forward return dates is a latent IC bias.
   - Recommendation: Use the OHLCV DataFrame itself to find the +5 trading day price (advance by 5 rows in the index), not a calendar offset. This is the most reliable approach.

3. **`backtest_signal_history` table creation timing**
   - What we know: `db/database.py::init_db()` must be extended to create the new table
   - What's unclear: Whether Phase 2 should add a migration function or extend the existing idempotent `CREATE TABLE IF NOT EXISTS` pattern
   - Recommendation: Follow the existing pattern — add `CREATE TABLE IF NOT EXISTS backtest_signal_history ...` in `init_db()`. No migration framework needed for additive tables.

---

## Sources

### Primary (HIGH confidence — verified by direct code inspection / tool)
- `engine/analytics.py` — current CVaR/VaR implementation (lines 516–524, Gaussian approximation confirmed)
- `backtesting/engine.py` — current backtester shape; no `cost_per_trade` parameter confirmed
- `tracking/tracker.py` — hit-rate tracking confirmed; no IC/Brier methods present
- `engine/weight_adapter.py` — EWMA accuracy weights confirmed; no IC integration present
- `data/investment_agent.db` — signal_history: 10 rows, single day, all outcomes NULL (confirmed by DB query 2026-04-21)
- `data/investment_agent.db` — price_history_cache: AAPL only, 959 rows, 2022-03-07 to 2025-12-30 (confirmed by DB query 2026-04-21)
- PyPI `pip index versions quantstats`: 0.0.81 is latest (confirmed 2026-04-21)
- PyPI scipy 1.15.3, numpy 2.2.6, arch 8.0.0 — confirmed installed via `pip show`
- QuantStats source inspection (https://raw.githubusercontent.com/ranaroussi/quantstats/main/quantstats/stats.py) — `cvar()`, `value_at_risk()` signatures confirmed

### Secondary (MEDIUM confidence — official docs / verified reference)
- Freqtrade fee docs (https://www.freqtrade.io/en/stable/configuration/) — `fee=0.001` default confirmed
- QuantStats GitHub (https://github.com/ranaroussi/quantstats) — active maintenance, Jan 2026 last release
- sklearn brier_score_loss docs (https://scikit-learn.org/stable/modules/generated/sklearn.metrics.brier_score_loss.html) — binary Brier formulation confirmed

### Tertiary (LOW confidence — web search / training knowledge)
- IC minimum sample size (N≥30 rule of thumb) — cited from http://mrzepczynski.blogspot.com/2024/03/the-information-coefficient-tell-me.html [CITED]
- Brier multi-class adaptation (one-vs-rest) — [ASSUMED from training knowledge; not directly cited from 2026 source]
- Walk-forward short window defensibility — [ASSUMED from general ML backtesting practice; specific citation not found for 30/10 windows]

---

## Metadata

**Confidence breakdown:**
- Standard stack (quantstats): HIGH — PyPI version confirmed, source inspected
- Current codebase state (no IC/Brier/costs): HIGH — direct file inspection
- signal_history data scarcity: HIGH — direct DB query
- Brier multi-class formulation: MEDIUM — standard practice, not project-specific citation
- IC minimum sample N≥30: MEDIUM — cited blog post, consistent with academic convention
- Walk-forward 30/10 window sizes: MEDIUM — reasonable given data availability, not validated empirically

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (QuantStats versioning stable; SQLite data confirmed day-of)
