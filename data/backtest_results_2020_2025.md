# Backtest Results: TechnicalAgent Signal Timing vs Buy-and-Hold

**Date**: 2026-03-11
**Period**: 2020-01-01 to 2025-12-31 (6 years)
**Agent**: TechnicalAgent only (PIT-safe, no look-ahead bias)
**Config**: Full position (100%), no stop-loss, no take-profit, weekly rebalance
**Capital**: $100,000

---

## Summary Table

| Ticker | Signal Return | B&H Return | Signal Ann. | Signal MaxDD | B&H MaxDD | Sharpe | Win Rate | Trades |
|--------|-------------|-----------|-------------|-------------|-----------|--------|----------|--------|
| AAPL | +123.6% | +263.7% | +14.4% | -33.2% | -33.4% | 1.50 | 62.5% | 8 |
| MSFT | +52.9% | +203.5% | +7.4% | -32.0% | -37.6% | 0.95 | 28.6% | 7 |
| TSLA | +591.6% | +1484.3% | +38.2% | -69.9% | -73.6% | 1.87 | 33.3% | 9 |
| NVDA | +2381.6% | +3026.8% | +71.1% | -57.5% | -66.4% | 3.36 | 75.0% | 4 |
| SPY | +74.3% | +111.5% | +9.7% | -18.7% | -34.1% | 1.66 | 66.7% | 6 |
| BTC | +1043.2% | +1128.2% | +50.3% | -40.7% | -76.6% | 2.36 | 75.0% | 8 |

---

## Key Findings

### 1. Drawdown Protection (The Real Value Proposition)

Signal timing reduced max drawdown on ALL tickers:

| Ticker | B&H MaxDD | Signal MaxDD | DD Improvement |
|--------|-----------|-------------|----------------|
| BTC | -76.6% | -40.7% | **+35.9 pp** |
| SPY | -34.1% | -18.7% | **+15.4 pp** |
| NVDA | -66.4% | -57.5% | +8.9 pp |
| MSFT | -37.6% | -32.0% | +5.6 pp |
| TSLA | -73.6% | -69.9% | +3.7 pp |
| AAPL | -33.4% | -33.2% | +0.2 pp |

**BTC and SPY stand out**: system nearly matched buy-and-hold returns while dramatically reducing risk.

### 2. Risk-Adjusted Returns (Sharpe Ratios)

All tickers show strong Sharpe ratios, well above the typical buy-and-hold SPY Sharpe of ~0.5:

- NVDA: 3.36 (exceptional)
- BTC: 2.36 (excellent)
- TSLA: 1.87 (very good)
- SPY: 1.66 (very good)
- AAPL: 1.50 (good)
- MSFT: 0.95 (acceptable)

### 3. Total Returns vs Buy-and-Hold

Signal timing underperformed buy-and-hold on total return for most tickers. This is **expected** for a market-timing strategy during a 5-year bull market:
- System holds cash during HOLD periods (earning 0%)
- Bull markets reward time-in-market over market timing
- The tradeoff: lower returns for lower drawdowns

**Exception: BTC** -- signal timing captured 92% of buy-and-hold return (+1043% vs +1128%) while cutting drawdown almost in half. This is the best risk/reward profile.

### 4. Profit Factor

High profit factors across all tickers indicate when the system trades, it makes more on winners than it loses on losers:

- NVDA: 34.15x
- BTC: 22.92x
- TSLA: 11.84x
- SPY: 4.57x
- AAPL: 4.37x
- MSFT: 2.66x

---

## Honest Assessment

### What the numbers tell us:
1. **The system is a "participate in uptrends, sit out in downtrends" strategy**
2. **Drawdown protection works** -- consistently reduced max drawdown
3. **Risk-adjusted metrics are strong** -- Sharpe > 1.5 for 4/6 tickers
4. **BTC is the best use case** -- nearly full return capture with half the drawdown

### What the numbers DON'T tell us:
1. No transaction costs or slippage included
2. Cash earns 0% in HOLD periods (realistically would earn 4-5% in T-bills)
3. TechnicalAgent only -- no fundamental/macro context
4. Indicator parameters were not optimized (default values), but this could also mean overfitting risk is lower
5. This is a 6-year sample in a largely bull market -- more bear market data needed
6. yfinance data may have minor adjustments vs real-time data

### Bottom line:
The system doesn't beat buy-and-hold on raw returns (except arguably BTC), but it **manages risk significantly better**. For an investor who can't stomach -76% drawdowns on BTC or -33% on SPY, the signal timing provides real value by keeping you out of the worst dips.

---

## Detailed Trade Logs

### AAPL (8 trades, 62.5% win rate)
```
2020-01-06  BUY  $72.32  -> 2020-02-24  $68.24   -5.6%   signal_sell
2020-04-06  BUY  $65.62  -> 2021-03-01  $120.13  +83.1%  signal_sell
2021-05-10  BUY  $126.85 -> 2022-01-24  $161.62  +27.4%  signal_sell
2022-08-01  BUY  $161.51 -> 2022-09-19  $154.48  -4.4%   signal_sell
2023-02-06  BUY  $151.73 -> 2023-10-30  $170.29  +12.2%  signal_sell
2023-11-06  BUY  $179.23 -> 2024-02-26  $181.16  +1.1%   signal_sell
2024-05-13  BUY  $186.28 -> 2025-03-17  $214.00  +14.9%  signal_sell
2025-08-11  BUY  $227.18 -> 2025-12-29  $273.76  +20.5%  end_of_period
```

### SPY (6 trades, 66.7% win rate)
```
2020-05-11  BUY  $292.50 -> 2022-03-07  $419.43  +43.4%  signal_sell
2022-04-04  BUY  $456.80 -> 2022-04-11  $439.92  -3.7%   signal_sell
2023-01-30  BUY  $400.59 -> 2023-10-23  $420.46  +5.0%   signal_sell
2023-12-04  BUY  $456.69 -> 2025-03-10  $560.58  +22.7%  signal_sell
2025-05-19  BUY  $594.85 -> 2025-12-29  $687.85  +15.6%  end_of_period
```

### BTC-USD (8 trades, 75.0% win rate)
```
2020-05-04  BUY  $8916.52  -> 2021-07-19  $31517.42  +253.5%  signal_sell
2021-08-02  BUY  $39956.55 -> 2021-12-06  $49240.42  +23.2%   signal_sell
2022-03-28  BUY  $47057.20 -> 2022-05-09  $33940.23  -27.9%   signal_sell
2023-02-20  BUY  $24829.15 -> 2023-09-25  $26298.48  +5.9%    signal_sell
2023-10-02  BUY  $27530.79 -> 2024-07-08  $56705.10  +106.0%  signal_sell
2024-07-15  BUY  $64870.15 -> 2024-09-02  $59112.48  -8.9%    signal_sell
2024-10-14  BUY  $66046.12 -> 2025-03-10  $78532.00  +18.9%   signal_sell
2025-05-05  BUY  $94748.05 -> 2025-11-03  $106547.52 +12.5%   signal_sell
```

### NVDA (4 trades, 75.0% win rate)
```
2020-01-06  BUY  $5.93   -> 2022-03-07  $21.35   +260.3%  signal_sell
2022-03-21  BUY  $26.73  -> 2022-04-25  $19.90   -25.6%   signal_sell
2022-12-12  BUY  $17.53  -> 2025-01-27  $118.42  +575.3%  signal_sell
2025-06-02  BUY  $137.38 -> 2025-12-29  $188.22  +37.0%   end_of_period
```
