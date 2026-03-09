## Architecture Review: SQLite Concurrency, Drift Edge Cases, Portfolio Edge Cases
---
### 1. SQLite Concurrency
**Critical: Async writers without WAL mode**
The daemon runs three concurrent async jobs that all write to the same SQLite file, but the architecture doesn't specify WAL mode. Default journal mode allows only one writer — concurrent writes from `daily_revaluation` + `catalyst_scan` overlap windows will serialize or fail with `database is locked`.

```python
# Missing from initialization:
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")  # retry for 5s before error
```

**Critical: Blocking sqlite3 in asyncio event loop**
Every `await self.data.get_price()` call is async, but the subsequent `self.store.save_alert()` / `self.store.save_portfolio_snapshot()` calls are not marked async. Standard `sqlite3` is blocking — calling it from an asyncio coroutine blocks the entire event loop during I/O. Need `aiosqlite` or offload to a thread pool executor.

**Race condition: partial portfolio snapshot**
In `daily_revaluation`, prices are updated sequentially in a `for pos in portfolio.positions` loop. If the loop fails midway (rate limit, network error), `save_portfolio_snapshot()` is presumably called at the end — but the architecture doesn't show a transaction wrapping the entire loop. A crash after updating 3 of 5 positions writes a snapshot with mixed old/new prices.

```python
# Needs explicit transaction:
async with db.transaction():
    for pos in portfolio.positions:
        pos.current_price = await self.data.get_price(pos.ticker)
        ...
    self.store.save_portfolio_snapshot(portfolio)
```

**Missing indexes on hot query paths**
`monitoring_alerts` will be queried constantly (`get_alerts(ticker, days=7)` runs for every position during weekly revaluation) but has no index defined on `(ticker, timestamp)`. With 6 months of daily alerts for 10 positions, this becomes a full table scan on every weekly job.

---
### 2. Drift Calculation Edge Cases
**Short position drift inversion**
`entry_drift_pct = (actual_entry - expected_entry) / expected_entry`
For a SHORT, paying a *higher* actual entry price than expected is *worse* execution, but the formula gives a positive number (same sign as a LONG getting a worse fill). `DriftAnalyzer` needs to sign-adjust based on `direction`:

```python
entry_drift_pct = (actual - expected) / expected
if direction == 'SHORT':
    entry_drift_pct = -entry_drift_pct
```
`return_drift` has the same issue — a LONG that returns -5% vs expected +10% has drift of -15%, whereas a SHORT in the same situation has drift that needs to account for direction.

**Stock split invalidation of expected prices**
When AAPL does a 4:1 split, `avg_cost` halves. But `expected_entry_price`, `expected_target_price`, and `expected_stop_loss` in `trade_records` are immutable snapshots. Post-split, `entry_drift_pct` compares post-split actual vs pre-split expected — the number is meaningless. The architecture mentions alerting on splits but explicitly says "system does not auto-adjust" — this needs a flag in `trade_records` like `adjusted_for_split BOOLEAN` so the drift engine can skip or recalculate those rows.

**Dividend omission in return drift**
`actual_return_pct` appears to be price return only. For a dividend-paying stock held 6 months, a 2–3% dividend yield is real return. If MSFT pays $1.10/share quarterly and you held 200 shares for 6 months, that's $440 missing from `actual_pnl_amount`, making the system look more optimistic than it is in drift analysis.

**Confidence calibration with sparse buckets**
The calibration chart has 5 buckets (50–60, 60–70, 70–80, 80–90, 90–100). With 47 total trades in the example, you get roughly 9 trades per bucket on average — but the distribution will be skewed (most signals likely 65–80), leaving some buckets with 2–3 samples. The chart will show apparent miscalibration that's just noise. Need minimum sample size guard:  

```python
if bucket.count < MIN_CALIBRATION_SAMPLE:  # suggest 20
    bucket.reliable = False  # render as dashed line / grayed out
```

**TIME_OVERRUN threshold on short-dated trades**
```python
if pos.holding_days > (pos.expected_hold_days or 999) * 1.5:
```
For a trade with `expected_hold_days = 3` (short-term technical play), the trigger fires at day 4 or 5. For a 2-day expected trade, it fires at day 3. These are hair-trigger alerts for any trade where the system suggested a short hold. The `or 999` fallback is also wrong — if `expected_hold_days` is NULL because no estimate was given, 999 × 1.5 = 1498 days before TIME_OVERRUN fires. Should be a configured default (e.g., 90 days) with a minimum floor (e.g., max(threshold, 7 days)).

**Open trades contaminating drift stats**
`compute_drift_stats(lookback=50)` — it's unclear whether open trades (outcome='OPEN') are filtered. Including them would contaminate `return_drift` with unrealized mid-trade noise. The `avg_return_drift: +3.2%` shown in the weekly report implies open trades are included (since you won't close 47 trades before the first weekly report). The engine must document its filtering logic explicitly.

**Trading days vs calendar days mismatch**
`expected_hold_days` is derived from `expected_hold_range = "3-6 months"`. Who does this conversion, and in what units? 3 months = 63 trading days or 90 calendar days. BTC never closes; stocks do. `hold_drift_days = actual_hold - expected_hold` will show a systematic +27-day bias for stocks simply from the conversion ambiguity, masking real timing miscalibration.

---
### 3. Portfolio Edge Cases
**Double-counting cash**
`Portfolio.cash: float` is a separate field, but `Position.asset_type` includes `'cash'`. The architecture is silent on whether cash-as-position and portfolio.cash coexist. If cash is tracked in both places and `total_value = sum(positions.market_value) + cash`, cash gets counted twice.

**Zero-quantity positions after partial exits**
The architecture doesn't define what happens when a position is partially closed (sell 1/3 at TP1). If the remaining 2/3 becomes a new record, stale zero-qty records could persist in the positions list. `sector_breakdown` iterates positions, so a zero-qty MSFT entry still contributes its sector tag but with zero market value — the sector percentage calculation is correct but `top_concentration` list would include a 0% MSFT entry.

**Portfolio scaling breaks historical drift**
`advisor portfolio scale --multiplier 2.0` doubles quantities. This doesn't update `expected_entry_price` or `expected_return_pct` in existing `trade_records`. Post-scale drift stats compare original-sizing expectations to double-sized actual PnL amounts — making `actual_pnl_amount` appear 2× the drift for pre-scale trades.

**BTC position sizing unit mismatch**
The GOOGL example outputs `"140 shares @ ~$180"`. BTC at $80,000 can't be expressed as shares. The `PositionSize` output format and the `advisor portfolio add --qty` CLI both need to handle fractional crypto units. More importantly, `max_single_position: 0.15` in portfolio constraints means a max position of ~$60K at $400K portfolio — that's 0.75 BTC. The size checker works in market value terms, not unit terms, so this should be fine, but the output formatting will be wrong.

**Beta calculation for BTC**
`beta_weighted: float | None` — BTC's beta vs SPX is highly regime-dependent (near 0 in 2020 pre-bull, ~1.5 during 2021 risk-on, sometimes negative during flight-to-safety). Using a trailing 1-year beta for BTC in the `Portfolio β: 1.12 → 1.19` calculation could be actively misleading. At minimum this needs a recency window (e.g., 90-day) and should be flagged as unreliable for crypto in the UI.

**Correlation matrix with 24/7 crypto vs market-hours stocks**
BTC weekend returns exist; stock weekend returns are zero (markets closed). A naive correlation using daily price series aligns Monday-to-Monday for stocks (which bundles Friday-close to Monday-open gap) against Monday-to-Monday for BTC (which has real 3 days of movement). The BTC–stock correlation will be systematically understated. Need to either use weekly returns for cross-asset correlation, or align timestamps explicitly.

**cash_pct drift without manual updates**
After executing a trade, `portfolio.cash` must be manually updated via CLI. If a user buys GOOGL for $25,200 but forgets `advisor portfolio set-cash`, `cash_pct = 30%` stays stale instead of updating to `21%`. All subsequent exposure calculations and "If you BUY X: After → Cash: 21%" calculations will be wrong. There's no reconciliation mechanism — the system can't detect the drift between stated cash and implied cash (total_value - sum(market_values)).

A simple sanity check would catch this:

```python
implied_cash = self.total_value - sum(p.market_value for p in self.positions)
if abs(implied_cash - self.cash) / self.total_value > 0.02:  # 2% threshold
    warn("Cash balance may be stale. Run 'portfolio reconcile'.")
```

**Marginal VaR with < 3 positions**
`marginal_var: float` in `PortfolioOverlay` — marginal VaR calculation requires a correlation matrix and covariance estimation. With 1–2 positions (common in Phase 1 while the system is new), the covariance matrix is either singular or statistically meaningless. Need a minimum-positions guard and a fallback to standalone position VaR when the portfolio is too small for matrix methods.

---
### Summary Table

| Area      | Issue                                             | Severity |
| --------- | ------------------------------------------------ | ---------- |
| SQLite    | No WAL mode, concurrent daemon jobs will deadlock | Critical   |
| SQLite    | Blocking sqlite3 in asyncio — blocks event loop | Critical   |
| SQLite    | No transaction wrapping daily_revaluation loop | High       |
| SQLite    | Missing index on monitoring_alerts(ticker, timestamp) | Medium     |
| Drift     | Short position sign inversion in entry/return drift | High       |
| Drift     | Stock splits invalidate expected_price fields | High       |
| Drift     | Open trades contaminate drift averages | High       |
| Drift     | Confidence calibration spurious with < 20 samples/bucket | Medium     |
| Drift     | TIME_OVERRUN fires on day 3 for 2-day expected trades | Medium     |
| Drift     | Trading days vs calendar days ambiguity in hold_drift | Medium     |
| Drift     | Dividend exclusion from actual_return_pct | Low        |
| Portfolio | Cash potentially double-counted | High       |
| Portfolio | Manual cash update creates silent drift in all exposure % | High       |
| Portfolio | Scaling operation breaks pre-scale drift metrics | High       |
| Portfolio | BTC–stock correlation understated (24/7 vs market hours) | Medium     |
| Portfolio | BTC beta unreliable, no recency window specified | Medium     |
| Portfolio | Marginal VaR undefined for < 3 positions | Medium     |
| Portfolio | Zero-qty positions after partial exits not cleaned up | Low        |
