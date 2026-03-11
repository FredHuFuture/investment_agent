# Task 015.5 -- FundamentalAgent Enhancement (3 New Metrics + Weight Tuning)

## Objective

Add three missing metrics to `FundamentalAgent` that are available via yfinance but currently unused: **PEG Ratio**, **Earnings Growth**, and **Analyst Rating**. Also add **Dividend Yield** to the scoring model (currently fetched but only displayed, not scored). Adjust the aggregator equity weights to increase fundamental influence.

**Rationale**: Comparing our scoring model against industry frameworks reveals these gaps. PEG captures growth-adjusted valuation (P/E alone is incomplete). Earnings growth is a direct profitability trajectory metric. Analyst consensus provides external validation. All three are available from `yfinance` at zero additional API cost.

---

## Scope

**Files to MODIFY (4):**

| File | Change |
|------|--------|
| `agents/fundamental.py` | Add PEG, earnings growth, analyst rating, dividend yield to scoring |
| `engine/aggregator.py` | Update equity weights from 0.35/0.35/0.30 to 0.45/0.30/0.25 |
| `cli/report.py` | Add new metrics to both standard and detail display |
| `tests/test_006_fundamental.py` | Add 4 new tests for new metrics |

**No new files. No new dependencies. No schema changes.**

---

## Detailed Design

### 1. `agents/fundamental.py` -- Add Metrics

#### 1a. New metrics to extract from `key_stats`

These yfinance fields are available in the `info` dict returned by `get_key_stats()`:

| yfinance field | Our metric key | Type |
|---------------|----------------|------|
| `pegRatio` | `peg_ratio` | float |
| `earningsGrowth` | `earnings_growth` | float (decimal, e.g. 0.15 = 15%) |
| `recommendationMean` | `analyst_rating` | float (1.0=Strong Buy to 5.0=Strong Sell) |

Extract these in the `analyze()` method alongside existing metrics:

```python
peg = key_stats.get("pegRatio")
earnings_growth = key_stats.get("earningsGrowth")
analyst_rating = key_stats.get("recommendationMean")
```

Add to `metrics` dict:
```python
metrics["peg_ratio"] = peg
metrics["earnings_growth"] = earnings_growth
metrics["analyst_rating"] = analyst_rating
```

#### 1b. Scoring additions

**PEG Ratio** -- add to Value sub-score:
```python
# PEG < 1.0 is undervalued relative to growth, > 2.0 is expensive
_score_linear(peg, bullish=1.0, bearish=2.5, max_score=15, min_score=-10, lower_is_better=True)
```

**Earnings Growth** -- add to Growth sub-score:
```python
# Similar to revenue growth but for earnings
if earnings_growth is not None:
    if earnings_growth > 0.30:    # >30% growth
        growth_score += 25
    elif earnings_growth > 0.10:  # >10% growth
        growth_score += 15
    elif earnings_growth >= 0:    # 0-10% growth
        growth_score += 5
    elif earnings_growth > -0.10: # slight decline
        growth_score -= 15
    else:                         # >10% decline
        growth_score -= 25
```

**Analyst Rating** -- add to Quality sub-score:
```python
# 1.0 = Strong Buy, 2.0 = Buy, 3.0 = Hold, 4.0 = Sell, 5.0 = Strong Sell
_score_linear(analyst_rating, bullish=1.5, bearish=3.5, max_score=10, min_score=-10, lower_is_better=True)
```

**Dividend Yield** -- add to Growth sub-score (currently fetched but not scored):
```python
# Modest bonus for yield, small penalty for zero yield in mature companies
if dividend_yield is not None and dividend_yield > 0.03:
    growth_score += 5
```

#### 1c. Guard for None values

All new metrics must be None-safe. If yfinance doesn't return a value, skip the scoring contribution (add 0). This matches existing patterns.

### 2. `engine/aggregator.py` -- Update Equity Weights

Change the stock weights to increase fundamental influence:

```python
# Before:
"stock": {"TechnicalAgent": 0.35, "FundamentalAgent": 0.35, "MacroAgent": 0.30}

# After:
"stock": {"TechnicalAgent": 0.30, "FundamentalAgent": 0.45, "MacroAgent": 0.25}
```

**Rationale**: For long-term equity investing at $200K-500K scale, fundamentals should be the primary driver. Technical and macro are supporting signals.

Crypto weights unchanged: `{"TechnicalAgent": 0.45, "MacroAgent": 0.55}`

### 3. `cli/report.py` -- Display New Metrics

#### 3a. Standard mode (`_format_agent_detail`)

Add PEG and earnings growth to the one-liner:
```python
# Before: P/E: 33.0 | ROE: 151.9% | Rev Growth: +6.4% | D/E: 1.34
# After:  P/E: 33.0 | PEG: 1.8 | ROE: 151.9% | EPS Gr: +15.0% | D/E: 1.34
```

Replace `Rev Growth` with `EPS Gr` (earnings growth) in the one-liner since it's more actionable. Revenue growth remains in detail mode.

#### 3b. Detail mode (`_append_fundamental_groups`)

Add to existing groups:
- **Valuation** group: add `PEG Ratio`
- **Quality** group: add `Analyst Rating` (format: "1.8 (Buy)")
- **Growth** group: add `Earnings Growth`

Analyst rating display helper:
```python
def _analyst_label(rating: float) -> str:
    if rating <= 1.5: return "Strong Buy"
    if rating <= 2.5: return "Buy"
    if rating <= 3.5: return "Hold"
    if rating <= 4.5: return "Sell"
    return "Strong Sell"
```

---

## Test Plan (4 new tests)

Add to `tests/test_006_fundamental.py`:

1. **`test_peg_ratio_scoring`** -- Mock key_stats with pegRatio=0.8 (cheap) and pegRatio=3.0 (expensive). Verify signal direction changes appropriately.

2. **`test_earnings_growth_scoring`** -- Mock earningsGrowth=0.35 (strong) vs earningsGrowth=-0.15 (contraction). Verify growth sub-score reflects this.

3. **`test_analyst_rating_scoring`** -- Mock recommendationMean=1.5 (Strong Buy) vs 4.5 (Sell). Verify quality sub-score adjusts.

4. **`test_missing_new_metrics_graceful`** -- Mock key_stats WITHOUT pegRatio/earningsGrowth/recommendationMean. Verify agent still works with no errors (None-safe guards).

---

## Integration Points

| Component | Impact |
|-----------|--------|
| `data_providers/yfinance_provider.py` | No changes -- `get_key_stats()` already returns full `info` dict |
| `cli/report.py` | Display updates (both standard + detail mode) |
| `engine/aggregator.py` | Weight change for equity |
| `backtesting/` | No impact -- backtester uses TechnicalAgent only |
| `monitoring/` | No impact -- monitoring checks prices, not fundamentals |

---

## Out of Scope

- Restructuring sub-scores into flat 11-metric model (future consideration)
- Adding sector-specific metric thresholds (Task 019)
- Universe-relative percentile ranking (requires multi-ticker context)
- Changing crypto agent weights or scoring

---

## Acceptance Criteria

1. `python -m cli.analyze_cli AAPL` -- shows PEG and earnings growth in one-liner
2. `python -m cli.analyze_cli AAPL --detail` -- shows all new metrics in expanded view
3. Stocks without PEG/earnings data (e.g., some small caps) -- no crash, graceful skip
4. All existing tests pass (129 passed baseline)
5. 4 new tests pass
6. Aggregator weights updated to 0.30/0.45/0.25 for equity
