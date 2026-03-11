# Investment Agent -- Usage Guide

## Quick Start

### 1. Install

```powershell
cd investment_agent
pip install -e ".[dev]"
```

Optional: set FRED API key for macro agent (free at https://fred.stlouisfed.org/docs/api/api_key.html):
```powershell
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

```powershell
# Set your cash position
python -m cli.portfolio_cli set-cash --amount 200000

# Add stock positions
python -m cli.portfolio_cli add --ticker AAPL --qty 100 --cost 185.50 --date 2026-01-15 --asset-type stock --sector Technology

python -m cli.portfolio_cli add --ticker MSFT --qty 50 --cost 410.00 --date 2026-02-01 --asset-type stock --sector Technology

# Add crypto
python -m cli.portfolio_cli add --ticker BTC-USD --qty 0.5 --cost 62000.00 --date 2026-01-20 --asset-type btc

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
BTC-USD  btc       0.50 $62,000.00    $31,000.00  -
---------------------------------------------------------------
Total Cost Basis: $70,050.00
Cash: $200,000.00
...
===============================================================
```

### Step 2: Analyze a Ticker Before Buying

```powershell
# Analyze a US stock
python -m cli.analyze_cli AAPL

# Analyze crypto
python -m cli.analyze_cli BTC --asset-type btc

# Get full agent breakdown (all metrics, reasoning, weight math)
python -m cli.analyze_cli AAPL --detail

# Short form
python -m cli.analyze_cli AAPL -d

# Get JSON output (for programmatic use)
python -m cli.analyze_cli MSFT --json
```

**Standard output** (`python -m cli.analyze_cli AAPL`):
```
================================================================
  ANALYSIS REPORT: Apple Inc. (AAPL)
================================================================

  Price:      $260.83
  Market Cap: $3.83T
  52W Range:  $169.21 - $288.62
  vs 52W High: -9.6%
  Sector:     Technology / Consumer Electronics

  SIGNAL:     HOLD
  CONFIDENCE: 70%
  REGIME:     NEUTRAL

----------------------------------------------------------------
  AGENT BREAKDOWN
----------------------------------------------------------------

  Technical:    HOLD (30%)
    RSI: 45.4 | Trend: +35 | Momentum: -20 | Volatility: +15

  Fundamental:  HOLD (48%)
    P/E: 33.0 | ROE: 151.9% | Rev Growth: +6.4% | D/E: 1.34

  Macro:        HOLD (30%)
    Regime: NEUTRAL | Score: +0

----------------------------------------------------------------
  CONSENSUS: 3/3 agents agree (strong consensus)
----------------------------------------------------------------

  WARNINGS:
    (none)

================================================================
```

**Detail output** (`python -m cli.analyze_cli AAPL --detail`):

Expands each agent to show:
- All sub-scores (Trend, Momentum, Volatility, etc.)
- All computed indicators (SMA 20/50/200, RSI, MACD, Bollinger Bands, etc.)
- Full reasoning narrative
- Weight contribution math (e.g., `0.35 x BUY(+1.0) x 72% conf = +0.2520`)
- AGGREGATION DETAIL section with raw score, consensus, and final calculation

**What to do with the signal:**
- **BUY (confidence > 65%)**: Consider entering or adding to position
- **BUY (confidence 50-65%)**: Weak signal, wait for confirmation
- **HOLD**: Keep current position, don't add
- **SELL (confidence > 65%)**: Consider reducing or exiting position
- **Low consensus warning**: Agents disagree, be cautious

### Step 3: Monitor Your Positions Daily

```powershell
# Run health check (fetches live prices, checks all exit triggers)
python -m cli.monitor_cli check
```

Output:
```
================================================================
  PORTFOLIO HEALTH CHECK
  2026-03-10 16:30:00 UTC
================================================================

  Positions checked: 3
  Alerts generated:  1

  [CRITICAL] AAPL -- STOP_LOSS_HIT
     AAPL hit stop loss $170.00 (current: $168.50, loss: -9.2%)
     -> CLOSE POSITION -- stop loss triggered

  Portfolio snapshot saved.
================================================================
```

```powershell
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

```powershell
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

## Charts & Visualization

Generate interactive plotly charts (opens in browser):

```powershell
# Price chart with technical indicators (candlestick + SMA + BB + RSI)
python -m cli.charts_cli analysis AAPL

# Portfolio allocation pie chart + sector exposure bar chart
python -m cli.charts_cli portfolio

# Signal confidence calibration chart
python -m cli.charts_cli calibration

# Expected vs actual return drift scatter chart
python -m cli.charts_cli drift

# Save without opening browser
python -m cli.charts_cli analysis AAPL --no-open
```

---

## Backtesting

Run walk-forward backtests to validate signal quality:

```powershell
# Basic backtest (technical agent only, safest -- no lookahead bias)
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31

# Custom configuration
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31 --agents technical --frequency weekly --capital 100000 --stop-loss 0.10 --take-profit 0.20

# Multi-agent backtest (note: fundamental agent uses non-PIT data)
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31 --agents technical,fundamental,macro
```

Output includes: Sharpe ratio, Sortino ratio, max drawdown, Calmar ratio, win rate, profit factor, CAGR, and trade log.

**Important**: When using FundamentalAgent in backtests, results carry a non-PIT disclaimer because yfinance financial data is not point-in-time. TechnicalAgent backtests are unaffected.

---

## Monitoring Daemon

Start the background daemon for automated daily/weekly monitoring:

```powershell
# Start with default schedule (daily 5 PM ET Mon-Fri, weekly Sat 10 AM ET)
python -m cli.daemon_cli start

# Custom schedule
python -m cli.daemon_cli start --daily-hour 16 --weekly-day sun --timezone US/Pacific

# Disable specific jobs
python -m cli.daemon_cli start --no-daily       # weekly only
python -m cli.daemon_cli start --no-weekly      # daily only

# Run a single job immediately (without starting daemon)
python -m cli.daemon_cli run-once daily
python -m cli.daemon_cli run-once weekly

# View execution history
python -m cli.daemon_cli status
```

**What the daemon does:**

| Job | Schedule | Description |
|-----|----------|-------------|
| Daily check | Mon-Fri 5 PM ET | Fetches prices, checks exit triggers, generates alerts |
| Weekly revaluation | Sat 10 AM ET | Re-runs full analysis per position, detects signal reversals |
| Catalyst scan | (disabled) | Stub -- requires LLM integration (Task 017) |

---

## Portfolio Management Commands

```powershell
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

## Recommended Routine

| When | Action | Command |
|------|--------|---------|
| Morning | Check overnight alerts | `python -m cli.monitor_cli alerts` |
| Morning | Run health check | `python -m cli.monitor_cli check` |
| Before trade | Analyze target ticker | `python -m cli.analyze_cli AAPL` |
| Before trade | Deep dive into analysis | `python -m cli.analyze_cli AAPL --detail` |
| After trade | Update portfolio | `portfolio_cli add/remove + set-cash` |
| Weekly | Review signal accuracy | `python -m cli.signal_cli stats` |
| Weekly | Check agent performance | `python -m cli.signal_cli agents` |
| Monthly | Review calibration | `python -m cli.signal_cli calibration` |
| Monthly | Run backtest on key holdings | `python -m cli.backtest_cli run AAPL --start ...` |

---

## All CLI Commands

| CLI | Command | Description |
|-----|---------|-------------|
| analyze_cli | `python -m cli.analyze_cli TICKER` | Single-ticker analysis |
| | `... --detail` / `-d` | Full agent breakdown |
| | `... --json` | JSON output |
| | `... --asset-type btc` | Crypto analysis |
| portfolio_cli | `... add` | Add position |
| | `... remove` | Remove position |
| | `... show` | View portfolio |
| | `... set-cash` | Set cash balance |
| | `... scale` | Scale all positions |
| | `... split` | Apply stock split |
| monitor_cli | `... check` | Run health check |
| | `... alerts` | View alerts |
| signal_cli | `... history` | Signal history |
| | `... stats` | Accuracy statistics |
| | `... calibration` | Confidence calibration |
| | `... agents` | Per-agent performance |
| charts_cli | `... analysis TICKER` | Price + indicator chart |
| | `... portfolio` | Allocation chart |
| | `... calibration` | Confidence calibration chart |
| | `... drift` | Expected vs actual drift scatter |
| backtest_cli | `... run TICKER` | Run walk-forward backtest |
| daemon_cli | `... start` | Start monitoring daemon |
| | `... run-once daily/weekly` | Run single job |
| | `... status` | View execution history |

---

## Important Notes

1. **Rule-based agents, no LLM**: Phase 1 uses technical indicators (RSI, SMA, MACD, Bollinger), fundamental metrics (P/E, revenue growth, debt/equity), and macro signals (VIX, yield curve, M2). LLM integration planned for Task 017.

2. **LONG positions only**: System only supports long positions in Phase 1. Short selling support planned for Phase 2.

3. **Not financial advice**: This is a monitoring and analysis tool. Always do your own research and consider your risk tolerance.

4. **Network required**: Analysis and monitoring commands fetch live data from Yahoo Finance and FRED. Monitor check will skip positions where price fetch fails.

5. **FRED API key optional**: Without it, MacroAgent is skipped. System works with Technical + Fundamental (stocks) or Technical only (crypto).

6. **Windows compatible**: All output uses ASCII characters (no emoji, no em dashes). Daemon handles Windows event loop policy automatically.

---

## File Locations

| What | Where |
|------|-------|
| Database | `data/investment_agent.db` |
| Daemon log | `data/daemon.log` |
| Config | `pyproject.toml` |
| Architecture docs | `docs/architecture_v5.md` |
| Task specs | `tasks/` |

## Running Tests

```powershell
pytest tests/ -v
```
Expected: 129 passed, 1 skipped (network test).
