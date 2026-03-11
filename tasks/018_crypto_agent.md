# Task 018 -- CryptoAgent: Dedicated 7-Factor Crypto Scoring

## Objective

Replace the current crypto analysis path (TechnicalAgent + MacroAgent only) with a dedicated `CryptoAgent` that implements 7 domain-specific scoring factors for cryptocurrency assets (BTC, ETH). The current approach applies stock-style technical indicators to crypto with zero crypto-native awareness.

**Rationale**: Crypto markets have fundamentally different drivers than equities -- no earnings, no balance sheets, but halving cycles, on-chain adoption, dominance shifts, and extreme volatility regimes matter. A dedicated scoring model will produce more actionable signals.

---

## Scope

**Files to CREATE (2):**

| File | Purpose |
|------|---------|
| `agents/crypto.py` | CryptoAgent with 7-factor scoring model |
| `tests/test_018_crypto_agent.py` | 10-12 tests |

**Files to MODIFY (4):**

| File | Change |
|------|--------|
| `agents/__init__.py` | Export CryptoAgent |
| `engine/pipeline.py` | Use CryptoAgent for btc/eth instead of TechnicalAgent+MacroAgent |
| `engine/aggregator.py` | Update crypto weights for 7-factor model |
| `cli/report.py` | Add CryptoAgent display in standard + detail mode |

---

## The 7-Factor Model

### Factor 1: Market Structure (15% weight)

Metrics (from yfinance + derived):
- **Market Cap Rank**: BTC=#1, ETH=#2 -- static for now, placeholder for future CMC API
- **BTC Dominance Proxy**: BTC market cap / (BTC + ETH market cap) -- available from yfinance
- **Supply Dynamics**: circulating supply / max supply ratio (scarcity measure)
  - BTC: 19.8M / 21M = 94% mined → bullish scarcity
  - ETH: no max supply → neutral

Scoring:
- High dominance (>60%) for BTC: +10 (flight to quality)
- High dominance (>60%) for ETH: -5 (risk-off rotation to BTC)
- Supply ratio > 90%: +10 (scarcity premium)
- Supply ratio < 50% or unlimited: 0 (neutral)

### Factor 2: Momentum & Trend (20% weight)

Metrics (from price history):
- **3-month return**: % change over 63 trading days
- **6-month return**: % change over 126 trading days
- **12-month return**: % change over 252 trading days
- **Distance from ATH**: current price / all-time-high - 1
- **200 DMA position**: price vs SMA(200)

Scoring:
- Each return period: positive = bullish points, negative = bearish points
- ATH distance < 10%: +15 (near ATH, strong trend)
- ATH distance > 50%: -10 (deep correction)
- Price > SMA200: +10, below: -10

### Factor 3: Volatility & Risk (15% weight)

Metrics (calculated from price history):
- **30-day annualized volatility**: std(daily returns) * sqrt(252)
- **Max drawdown (90 days)**: worst peak-to-trough in last 90 days
- **Sharpe ratio (90 days)**: (annualized return - risk_free) / annualized vol
- **Recovery time**: days since last 20%+ drawdown

Scoring:
- Vol < 40%: +10 (low for crypto)
- Vol 40-80%: 0 (normal)
- Vol > 80%: -15 (extreme)
- Max DD < 15%: +10, > 30%: -15
- Sharpe > 1.5: +15, < 0: -10
- Recovery > 60 days: +5 (stability), < 14 days from big drop: -10

### Factor 4: Liquidity & Volume (10% weight)

Metrics (from yfinance):
- **Average daily volume (20-day)**: absolute USD volume
- **Volume trend**: current 5-day avg vs 20-day avg
- **Turnover ratio**: volume / market cap

Scoring:
- Volume > $1B/day: +10 (highly liquid, BTC/ETH always qualify)
- Volume trend > 1.5x: +5 (increasing interest)
- Volume trend < 0.5x: -5 (fading interest)
- Turnover > 5%: +5 (active trading)

### Factor 5: Macro & Correlation (15% weight)

Metrics (from FRED + price history):
- **Correlation to S&P 500 (90-day rolling)**: pearson correlation
- **VIX sensitivity**: does crypto drop when VIX spikes?
- **Rate environment**: fed funds rate direction (from MacroAgent data)

Scoring:
- Low S&P correlation (<0.3): +10 (diversification value)
- High S&P correlation (>0.7): -5 (no diversification benefit)
- VIX > 30 + crypto down: -10 (risk-off contagion)
- Rate decreasing: +10 (liquidity expanding, good for crypto)
- Rate increasing: -5 (tightening)

### Factor 6: Network & Adoption (10% weight)

Metrics (static/semi-static, updateable):
- **Asset age**: years since genesis block (maturity proxy)
- **ETF access**: boolean (BTC spot ETF approved Jan 2024, ETH May 2024)
- **Regulatory status**: enum (FAVORABLE / NEUTRAL / HOSTILE)
- **Bear market survival count**: number of 70%+ drawdowns survived

For Phase 1, these are hardcoded constants:
```python
CRYPTO_ADOPTION = {
    "btc": {"age_years": 16, "etf_access": True, "regulatory": "FAVORABLE", "bear_survivals": 5},
    "eth": {"age_years": 10, "etf_access": True, "regulatory": "NEUTRAL", "bear_survivals": 4},
}
```

Scoring:
- Age > 10 years: +10 (battle-tested)
- ETF access: +10 (institutional adoption)
- Regulatory FAVORABLE: +5, HOSTILE: -10
- Bear survivals >= 4: +10 (antifragile)

### Factor 7: Cycle & Timing (15% weight)

Metrics (derived):
- **BTC halving cycle position**: months since last halving / 48 (cycle length)
  - Last halving: April 2024 (block 840,000)
  - Position 0.0-0.25 = early cycle (bullish historically)
  - Position 0.25-0.50 = mid cycle (peak zone)
  - Position 0.50-0.75 = late cycle (caution)
  - Position 0.75-1.0 = bear phase (risk-off)
- **Fear & Greed proxy**: derived from VIX + volume + momentum composite
- **Monthly seasonality**: historical monthly return averages

Scoring:
- Early cycle (0-12 months post-halving): +15
- Mid cycle (12-24 months): +5
- Late cycle (24-36 months): -5
- Bear phase (36-48 months): -15
- Fear & Greed proxy < 25 (extreme fear): +10 (contrarian buy)
- Fear & Greed proxy > 75 (extreme greed): -10 (caution)

---

## Composite Score Calculation

```python
composite = (
    market_structure * 0.15 +
    momentum_trend * 0.20 +
    volatility_risk * 0.15 +
    liquidity_volume * 0.10 +
    macro_correlation * 0.15 +
    network_adoption * 0.10 +
    cycle_timing * 0.15
)
```

Each factor score: [-100, +100], clamped.
Composite range: [-100, +100].

Signal thresholds:
- composite >= 20: BUY
- composite <= -20: SELL
- else: HOLD

Confidence: same formula as FundamentalAgent.

---

## Pipeline Integration

For crypto assets (btc, eth):
- **Before**: TechnicalAgent(0.45) + MacroAgent(0.55)
- **After**: CryptoAgent(1.0) -- single agent, 7 internal factors

The CryptoAgent is self-contained; it does NOT use the aggregator's multi-agent weighted average. It returns a single AgentOutput with the composite score. The aggregator passes it through as-is (similar to how a single-agent analysis works today).

Alternative: Split into CryptoTechnicalAgent + CryptoMacroAgent + CryptoFundamentalAgent. But this adds complexity without benefit -- the 7-factor model is better as a unified scoring system.

---

## Data Dependencies

| Data | Source | Available? |
|------|--------|-----------|
| Price history (OHLCV) | yfinance (BTC-USD, ETH-USD) | Yes |
| Market cap, volume | yfinance `.info` | Yes |
| Supply stats | yfinance `.info` (circulatingSupply, maxSupply) | Yes |
| S&P 500 prices | yfinance (^GSPC) | Yes |
| VIX | yfinance (^VIX) or FRED | Yes |
| Fed funds rate | FRED | Yes (Task 015.5 ensures key is set) |
| Halving dates | Hardcoded constant | Yes |
| Adoption metrics | Hardcoded constants | Yes |

No new API dependencies required.

---

## Test Plan (10-12 tests)

1. `test_crypto_agent_btc_basic` -- BTC analysis returns valid AgentOutput
2. `test_crypto_agent_eth_basic` -- ETH analysis returns valid AgentOutput
3. `test_market_structure_scoring` -- Mock data with varying dominance/supply
4. `test_momentum_multi_timeframe` -- Mock 3/6/12mo returns, verify scoring
5. `test_volatility_risk_metrics` -- Mock price series with known vol/drawdown
6. `test_liquidity_scoring` -- Mock volume data, verify turnover/trend scoring
7. `test_macro_correlation` -- Mock S&P + crypto returns, verify correlation calc
8. `test_network_adoption_constants` -- Verify BTC/ETH adoption scores
9. `test_cycle_timing_halving` -- Test different cycle positions (mock dates)
10. `test_fear_greed_proxy` -- Test extreme fear/greed conditions
11. `test_missing_data_graceful` -- Provider returns partial data, no crash
12. `test_unsupported_asset_type` -- stock/forex rejected with proper error

---

## Out of Scope

- On-chain metrics (active addresses, hash rate) -- requires blockchain API (Phase 3)
- Real Fear & Greed Index API -- use proxy for now
- Alt-coins beyond BTC/ETH -- Phase 3
- CoinMarketCap API integration -- future enhancement for market cap rankings
- Portfolio correlation (correlation to user's stock holdings) -- Task 019

---

## Acceptance Criteria

1. `python -m cli.analyze_cli btc` -- uses CryptoAgent, shows 7-factor breakdown
2. `python -m cli.analyze_cli btc --detail` -- shows all factors with metrics
3. `python -m cli.analyze_cli AAPL` -- unchanged (still uses Technical+Fundamental+Macro)
4. All existing tests pass (baseline)
5. 10+ new tests pass
6. CryptoAgent handles missing data gracefully (yfinance gaps)
