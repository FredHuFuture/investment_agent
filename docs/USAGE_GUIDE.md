# Investment Agent v4 — Usage Guide

## Quick Start

### 1. Install

```bash
cd investment_agent
pip install -e ".[dev]"
```

Optional: set FRED API key for macro agent (free at https://fred.stlouisfed.org/docs/api/api_key.html):
```bash
export FRED_API_KEY=your_key_here        # Mac/Linux
set FRED_API_KEY=your_key_here           # Windows CMD
$env:FRED_API_KEY="your_key_here"        # PowerShell
```
Without FRED key, the macro agent will be skipped (system still works with Technical + Fundamental only).

### 2. Initialize Database

Database auto-initializes on first CLI command. Default location: `data/investment_agent.db`.

---

## Daily Workflow

### Step 1: Set Up Your Portfolio

```bash
# Set your cash position
python -m cli.portfolio_cli set-cash --amount 200000

# Add stock positions
python -m cli.portfolio_cli add \
  --ticker AAPL --qty 100 --cost 185.50 --date 2026-01-15 \
  --asset-type stock --sector Technology

python -m cli.portfolio_cli add \
  --ticker MSFT --qty 50 --cost 410.00 --date 2026-02-01 \
  --asset-type stock --sector Technology

python -m cli.portfolio_cli add \
  --ticker GOOGL --qty 30 --cost 175.00 --date 2026-02-10 \
  --asset-type stock --sector Technology

# Add crypto
python -m cli.portfolio_cli add \
  --ticker BTC-USD --qty 0.5 --cost 62000.00 --date 2026-01-20 \
  --asset-type btc

# View portfolio
python -m cli.portfolio_cli show
```

Output:
```
===============================================================
 PORTFOLIO OVERVIEW
===============================================================
Ticker   Type     Qty     Avg Cost    Cost Basis  Sector
---------------------------------------------------------------
AAPL     stock   100.00   $185.50     $18,550.00  Technology
MSFT     stock    50.00   $410.00     $20,500.00  Technology
GOOGL    stock    30.00   $175.00      $5,250.00  Technology
BTC-USD  btc       0.50 $62,000.00    $31,000.00  -
---------------------------------------------------------------
Total Cost Basis: $75,300.00
Cash: $200,000.00
...
===============================================================
```

### Step 2: Analyze a Ticker Before Buying

```bash
# Analyze a US stock
python -m cli.analyze_cli AAPL

# Analyze crypto
python -m cli.analyze_cli BTC-USD --asset-type btc

# Get JSON output (for programmatic use)
python -m cli.analyze_cli MSFT --json
```

Output:
```
================================================================
  INVESTMENT ANALYSIS: AAPL (stock)
================================================================

  Signal: BUY   Confidence: 72.0%
  Regime: RISK_ON

  Agent Breakdown:
    Technical:    BUY  (68%)  RSI=45, SMA trend bullish
    Fundamental:  BUY  (75%)  P/E=28, revenue growth 8%
    Macro:        HOLD (55%)  VIX=18, yield curve normal

  Consensus: 2/3 agents agree
  ...
================================================================
```

**What to do with the signal:**
- **BUY (confidence > 65%)**: Consider entering or adding to position
- **BUY (confidence 50-65%)**: Weak signal, wait for confirmation
- **HOLD**: Keep current position, don't add
- **SELL (confidence > 65%)**: Consider reducing or exiting position
- **Low consensus warning**: Agents disagree, be cautious

### Step 3: Monitor Your Positions Daily

```bash
# Run health check (fetches live prices, checks all exit triggers)
python -m cli.monitor_cli check
```

Output:
```
================================================================
  PORTFOLIO HEALTH CHECK
  2026-03-10 16:30:00 UTC
================================================================

  Positions checked: 4
  Alerts generated:  1

  🔴 CRITICAL   AAPL — STOP_LOSS_HIT
     AAPL hit stop loss $170.00 (current: $168.50, loss: -9.2%)
     → CLOSE POSITION — stop loss triggered

  Portfolio snapshot saved.
================================================================
```

```bash
# View recent alerts
python -m cli.monitor_cli alerts

# Filter by ticker
python -m cli.monitor_cli alerts --ticker AAPL

# Filter by severity
python -m cli.monitor_cli alerts --severity CRITICAL
```

**Alert types and what to do:**

| Alert | Severity | Action |
|-------|----------|--------|
| STOP_LOSS_HIT | CRITICAL | Exit immediately. Your stop loss was hit. |
| TARGET_HIT | INFO | Consider taking profit. Your target price was reached. |
| TIME_OVERRUN | WARNING | Review thesis. Held much longer than expected. |
| SIGNIFICANT_LOSS | HIGH | Review position. Down >15% from entry. |
| SIGNIFICANT_GAIN | INFO | Consider partial profit-taking. Up >25% from entry. |

### Step 4: Track Signal Quality Over Time

After multiple analyses and trades, review how accurate the system is:

```bash
# View signal history
python -m cli.signal_cli history
python -m cli.signal_cli history --ticker AAPL
python -m cli.signal_cli history --signal BUY

# View accuracy statistics
python -m cli.signal_cli stats

# View confidence calibration (is the system overconfident?)
python -m cli.signal_cli calibration

# View per-agent performance (which agent is most accurate?)
python -m cli.signal_cli agents
```

---

## Portfolio Management Commands

```bash
# Remove a position (after selling)
python -m cli.portfolio_cli remove --ticker AAPL

# Update cash after a trade
python -m cli.portfolio_cli set-cash --amount 218550

# Apply a stock split (e.g., 4:1 split)
python -m cli.portfolio_cli split --ticker AAPL --ratio 4

# Scale portfolio for paper trading (e.g., 0.1x = $20K paper portfolio)
python -m cli.portfolio_cli scale --multiplier 0.1
```

---

## Recommended Daily Routine

| Time | Action | Command |
|------|--------|---------|
| Morning | Check overnight alerts | `python -m cli.monitor_cli alerts` |
| Morning | Run health check | `python -m cli.monitor_cli check` |
| Before trade | Analyze target ticker | `python -m cli.analyze_cli AAPL` |
| After trade | Update portfolio | `portfolio_cli add/remove + set-cash` |
| Weekly | Review signal accuracy | `python -m cli.signal_cli stats` |
| Weekly | Check agent performance | `python -m cli.signal_cli agents` |
| Monthly | Review calibration | `python -m cli.signal_cli calibration` |

---

## Important Notes

1. **Rule-based agents, no LLM**: Phase 1 uses technical indicators (RSI, SMA, MACD, Bollinger), fundamental metrics (P/E, revenue growth, debt/equity), and macro signals (VIX, yield curve, M2). No AI interpretation yet.

2. **LONG positions only**: System only supports long positions in Phase 1. Short selling support is planned for Phase 2.

3. **Not financial advice**: This is a monitoring and analysis tool. Always do your own research and consider your risk tolerance.

4. **Network required**: Analysis and monitoring commands fetch live data from Yahoo Finance, ccxt, and FRED. Monitor check will skip positions where price fetch fails.

5. **Signal tracking is manual for now**: Signals are saved when using the tracking API. Automatic pipeline integration (save every analysis run) is planned for Phase 2.

---

## File Locations

| What | Where |
|------|-------|
| Database | `data/investment_agent.db` |
| Config | `pyproject.toml` |
| Architecture docs | `docs/architecture_v4.md` |
| Task specs | `tasks/` |

## Running Tests

```bash
pytest tests/ -v
```
Expected: 94 passed, 2 skipped (network tests).
