# Task 019 -- Sector Rotation & Correlation Module

## Objective

Add sector-aware analysis to the equity pipeline: a **sector rotation modifier** that adjusts the final signal based on current macro regime + sector positioning, and a **portfolio correlation tracker** that flags concentration risk when assets move together.

**Rationale**: Our current system treats all stocks identically regardless of sector. In a rate-hiking cycle, Utilities and REITs behave very differently from Tech. A sector modifier of -30% to +30% can meaningfully improve signal accuracy. Correlation tracking prevents the portfolio from becoming a single bet.

---

## Scope

**Files to CREATE (3):**

| File | Purpose |
|------|---------|
| `engine/sector.py` | Sector rotation matrix + modifier calculation |
| `engine/correlation.py` | Portfolio correlation tracker |
| `tests/test_019_sector_correlation.py` | 8-10 tests |

**Files to MODIFY (3):**

| File | Change |
|------|--------|
| `engine/pipeline.py` | Apply sector modifier to aggregated signal |
| `engine/aggregator.py` | Accept optional sector_modifier in aggregation |
| `cli/report.py` | Display sector modifier and correlation warnings |

---

## Detailed Design

### 1. Sector Rotation Matrix (`engine/sector.py`)

#### 1a. Regime-Sector Mapping

A static matrix mapping macro regimes to sector modifiers:

```python
# Modifier values: -30 to +30 (percentage points applied to confidence)
SECTOR_ROTATION_MATRIX = {
    "RISK_ON": {
        "Technology": +20,
        "Consumer Cyclical": +15,
        "Financial Services": +10,
        "Industrials": +10,
        "Communication Services": +10,
        "Basic Materials": +5,
        "Energy": +5,
        "Healthcare": 0,
        "Consumer Defensive": -10,
        "Utilities": -15,
        "Real Estate": -10,
    },
    "RISK_OFF": {
        "Technology": -15,
        "Consumer Cyclical": -20,
        "Financial Services": -10,
        "Industrials": -10,
        "Communication Services": -5,
        "Basic Materials": -10,
        "Energy": -5,
        "Healthcare": +10,
        "Consumer Defensive": +20,
        "Utilities": +15,
        "Real Estate": +5,
    },
    "NEUTRAL": {
        # All sectors get 0 modifier in neutral regime
    },
}
```

#### 1b. API

```python
def get_sector_modifier(sector: str | None, regime: str) -> int:
    """Return sector rotation modifier in range [-30, +30].

    Args:
        sector: Sector name from yfinance (e.g., "Technology").
        regime: Macro regime from MacroAgent ("RISK_ON", "RISK_OFF", "NEUTRAL").

    Returns:
        Integer modifier to apply to signal confidence.
        Returns 0 if sector is None or not in matrix.
    """
```

#### 1c. Application

The sector modifier adjusts the **aggregated signal confidence**, not the signal direction:
```python
adjusted_confidence = base_confidence + sector_modifier
adjusted_confidence = max(30, min(90, adjusted_confidence))
```

A +20 modifier means "this sector is favored in current regime, increase conviction."
A -20 modifier means "this sector faces headwinds, reduce conviction."

If the modifier is large enough to push a borderline BUY/SELL into HOLD range, the signal may flip -- but this is handled by the aggregator's existing threshold logic.

### 2. Portfolio Correlation Tracker (`engine/correlation.py`)

#### 2a. Correlation Calculation

```python
async def calculate_portfolio_correlations(
    tickers: list[str],
    provider: DataProvider,
    lookback_days: int = 90,
) -> dict[str, Any]:
    """Calculate pairwise correlations for portfolio positions.

    Returns:
        {
            "correlation_matrix": {("AAPL", "MSFT"): 0.85, ...},
            "avg_correlation": 0.72,
            "high_correlation_pairs": [("AAPL", "MSFT", 0.85), ...],
            "concentration_risk": "HIGH" | "MODERATE" | "LOW",
            "warnings": ["AAPL-MSFT correlation 0.85 (>0.70)"]
        }
    """
```

#### 2b. Concentration Risk Thresholds

- Avg correlation > 0.70: **HIGH** -- portfolio moves as a block
- Avg correlation 0.40-0.70: **MODERATE** -- some diversification
- Avg correlation < 0.40: **LOW** -- well diversified

#### 2c. Integration Point

Correlation is calculated on-demand (not per-analysis) via a new CLI subcommand or as part of the monitor check. It adds warnings to the analysis report when a ticker has high correlation (>0.70) with multiple other portfolio positions.

### 3. Report Integration

#### 3a. Sector modifier display

After the AGGREGATION DETAIL section:
```
  SECTOR ADJUSTMENT
    Sector:     Technology
    Regime:     RISK_ON
    Modifier:   +20 (sector favored in current regime)
    Adjusted:   72% -> 82% confidence
```

In standard mode, add a single line:
```
  Sector Adj: +20 (Technology in RISK_ON)
```

#### 3b. Correlation warnings

If the analyzed ticker has high correlation with portfolio positions:
```
  WARNINGS:
    AAPL-MSFT correlation 0.85 -- consider diversification
```

---

## Test Plan (8-10 tests)

1. `test_sector_modifier_risk_on` -- Technology in RISK_ON gets +20
2. `test_sector_modifier_risk_off` -- Technology in RISK_OFF gets -15
3. `test_sector_modifier_neutral` -- Any sector in NEUTRAL gets 0
4. `test_sector_modifier_unknown_sector` -- Unknown/None sector returns 0
5. `test_sector_modifier_confidence_clamp` -- Modifier doesn't push confidence beyond [30, 90]
6. `test_correlation_calculation` -- Known price series → expected correlation
7. `test_concentration_risk_high` -- Avg corr > 0.70 → HIGH risk
8. `test_concentration_risk_low` -- Diverse portfolio → LOW risk
9. `test_correlation_missing_data` -- Partial price data handled gracefully
10. `test_sector_display_standard` -- Report shows sector adjustment line

---

## Data Dependencies

| Data | Source | Available? |
|------|--------|-----------|
| Sector | yfinance `.info["sector"]` | Yes (already fetched in pipeline ticker_info) |
| Regime | MacroAgent output | Yes |
| Portfolio positions | `portfolio/manager.py` | Yes |
| Price history for correlation | yfinance via DataProvider | Yes |

No new API dependencies.

---

## Out of Scope

- RSS/news sentiment per sector (Task 017 LLM integration)
- Dynamic sector rotation matrix (learning from history) -- Phase 3
- Cross-asset correlation (stock-crypto) -- included in Task 018 CryptoAgent
- Sector ETF momentum (SPDRs) -- future enhancement
- Real-time sector fund flow data -- requires paid data source

---

## Acceptance Criteria

1. `python -m cli.analyze_cli AAPL --detail` -- shows sector adjustment section
2. Sector modifier correctly varies by regime (positive in RISK_ON for Tech, negative in RISK_OFF)
3. Unknown sectors handled gracefully (modifier = 0)
4. Correlation calculation works for 2+ ticker portfolio
5. All existing tests pass
6. 8+ new tests pass
