<div align="center">

# Investment Agent

### The investment journal that fights back.

Tracks your thesis, monitors positions, tells you when reality diverges from your plan.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org) [![License MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE) [![Tests 217 passing](https://img.shields.io/badge/Tests-217_passing-brightgreen)](#) [![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)](http://localhost:8000/docs)

[Live Site](https://investment-agent.dev) · [Architecture](docs/architecture_v5.md) · [API Docs (local)](http://localhost:8000/docs)

</div>

---

<div align="center">
<img src="https://investment-agent.dev/gifs/analysis-demo.gif" alt="Multi-Agent Analysis Demo" width="720" />

*Enter any ticker → 4 agents analyze independently → weighted signal with confidence*
</div>

## Why This Exists

Most tools tell you what to buy. None track **why you bought** and whether that reason still holds.

- You set a thesis at entry: "NVDA will grow 30% on AI demand, hold 12 months"
- The system monitors continuously and alerts when reality diverges
- 4 specialized agents provide objective analysis while you stay emotional

> Unlike point-in-time screeners, this system maintains context about your positions over time. It remembers your thesis and tells you when you should reconsider.

**Value proposition = drawdown protection.** Backtested across 6 tickers (2020-2025), signal timing reduces max drawdown by 15-36 percentage points on every ticker while capturing the majority of upside. [See results →](#backtesting-results)

## Quick Start

```bash
git clone https://github.com/FredHuFuture/investment_agent.git
cd investment_agent

# Install
pip install --pre -e ".[dev]"
cd frontend && npm install && cd ..

# Seed demo portfolio (AAPL, NVDA, BTC, GS, MSFT)
python seed.py

# Start
make run-backend   # Terminal 1 → API on :8000
make run-frontend  # Terminal 2 → Dashboard on :3000
```

Open **http://localhost:3000** for the dashboard, or **http://localhost:8000/docs** for the interactive API.

Want to see everything without the frontend? Run `python demo.py` — it creates a temporary database, adds positions, runs analysis, monitoring, and a backtest in one script.

## Features

<table>
<tr>
<td width="50%">

### Multi-Agent Analysis
4 agents — Technical, Fundamental, Macro, Crypto — analyze each position from different angles, then aggregate into a single weighted signal.

<img src="https://investment-agent.dev/gifs/analysis-demo.gif" alt="Analysis" width="100%" />

</td>
<td width="50%">

### Walk-Forward Backtesting
Validate signals against 5 years of data. Point-in-time safe engine prevents look-ahead bias. Batch compare across tickers and agent combos.

<img src="https://investment-agent.dev/gifs/backtest-demo.gif" alt="Backtest" width="100%" />

</td>
</tr>
<tr>
<td width="50%">

### Portfolio Dashboard
Allocation breakdown, P&L metrics, recent alerts, signal summary — all at a glance.

<img src="https://investment-agent.dev/gifs/dashboard-demo.gif" alt="Dashboard" width="100%" />

</td>
<td width="50%">

### Continuous Monitoring
Background daemon watches positions 24/7. Alerts on price targets, drawdowns, signal reversals, and stop-loss triggers.

<img src="https://investment-agent.dev/gifs/monitoring-demo.gif" alt="Monitoring" width="100%" />

</td>
</tr>
</table>

**Also includes:** Thesis drift tracking · AI weekly summaries (Claude) · Interactive Plotly charts · Signal accuracy calibration · Adaptive weight optimization · Sector rotation & correlation analysis

## CLI Usage

```bash
# Analyze a stock
python -m cli.analyze_cli AAPL

# Analyze crypto (auto-detects, uses 7-factor CryptoAgent)
python -m cli.analyze_cli BTC

# Full sub-score breakdown
python -m cli.analyze_cli AAPL --detail

# Portfolio overview
python -m cli.portfolio_cli show

# Walk-forward backtest
python -m cli.backtest_cli run --ticker AAPL --start 2020-01-01 --end 2025-12-31

# Batch backtest + optimize weights
python -m cli.backtest_cli optimize --tickers AAPL,MSFT,BTC --start 2020-01-01 --end 2025-12-31

# Interactive chart (opens in browser)
python -m cli.charts_cli analysis AAPL

# Start monitoring daemon
python -m cli.daemon_cli start
```

## Architecture

```
DataProviders (YFinance, FRED)
        │
        ▼
┌──────────────┐  ┌──────────────────┐
│ Technical    │  │ Fundamental      │
│ 17 metrics   │  │ 20 metrics       │
│ SMA,RSI,MACD │  │ P/E,PEG,debt,div│
└──────┬───────┘  └────────┬─────────┘
       │                   │
       ▼                   ▼
┌──────────────┐  ┌──────────────────┐
│ Macro        │  │ Crypto           │
│ 11 metrics   │  │ 7-factor model   │
│ Yield,VIX,CLI│  │ BTC/ETH specific │
└──────┬───────┘  └────────┬─────────┘
       │                   │
       └─────────┬─────────┘
                 ▼
        ┌────────────────┐
        │ Aggregator     │
        │ Weighted avg + │
        │ consensus      │
        └───────┬────────┘
                │
       ┌────────┼──────────────┐
       ▼        ▼              ▼
   Portfolio  Signal       Claude API
   + Thesis   Tracking     Weekly Summary
   → Drift    → Accuracy
```

| Agent | Metrics | Focus |
|-------|---------|-------|
| **Technical** | 17 | SMA crossovers, RSI, MACD, Bollinger, ADX, volume |
| **Fundamental** | 20 | P/E, PEG, earnings growth, debt/equity, dividends (30/45/25 growth-value-quality) |
| **Macro** | 11 | Yield curve, VIX regime, CLI, unemployment, monetary policy via FRED |
| **Crypto** | 7 | Momentum, volatility regime, trend, volume, drawdown, mean reversion, macro correlation |

## Backtesting Results

Validated across 6 tickers (2020-2025, TechnicalAgent only):

| Ticker | Return | vs B&H | Max Drawdown | DD Improvement | Sharpe |
|--------|--------|--------|--------------|----------------|--------|
| NVDA | +4,892% | -223pp | -35.2% | **+30.8pp** | 3.36 |
| BTC | +1,043% | -85pp | -40.7% | **+35.9pp** | 2.36 |
| TSLA | +812% | -187pp | -52.1% | **+19.5pp** | 1.87 |
| SPY | +78% | -19pp | -18.7% | **+15.4pp** | 1.66 |
| AAPL | +231% | -107pp | -23.2% | **+16.8pp** | 1.50 |
| MSFT | +118% | -84pp | -31.2% | **+20.5pp** | 0.95 |

**Key insight:** Signal timing consistently reduces max drawdown by 15-36 percentage points across all tickers while capturing the majority of upside. The value prop is risk management, not alpha generation.

```bash
# Run your own backtest
python -m cli.backtest_cli run --ticker AAPL --start 2020-01-01 --end 2025-12-31
```

## Configuration

```bash
cp .env.example .env
```

| Variable | Required | Purpose |
|----------|----------|---------|
| `FRED_API_KEY` | For macro analysis | Free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `ANTHROPIC_API_KEY` | For AI summaries | Claude weekly portfolio review (~$0.03/run) |

Everything works without API keys except MacroAgent (needs FRED) and AI summaries (needs Claude).

## Project Structure

```
investment_agent/
  agents/           # 5 analysis agents (technical, fundamental, macro, crypto, summary)
  engine/           # Pipeline, aggregator, drift analyzer, weight optimizer
  portfolio/        # Position management + thesis tracking
  monitoring/       # Real-time alerts (price, drift, time overrun)
  tracking/         # Signal accuracy + calibration
  backtesting/      # Walk-forward engine + batch runner
  api/              # FastAPI REST backend (17 endpoints)
  frontend/         # React 18 + TypeScript + Tailwind dashboard
  daemon/           # APScheduler background monitoring
  data_providers/   # YFinance, FRED, CCXT abstraction
  charts/           # Plotly interactive chart generators
  cli/              # CLI entry points
  db/               # SQLite with WAL mode (9 tables)
  tests/            # 217 tests
```

## Tech Stack

Python 3.11+ · FastAPI · SQLite · React 18 · TypeScript · Tailwind CSS · Recharts · Plotly · yfinance · FRED

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions.

Good first issues: new technical indicators · additional data providers · frontend improvements · portfolio performance tracking · options support

## Disclaimer

This is a portfolio monitoring and analysis tool, not investment advice. All analysis is for informational purposes only. Do your own research.

## License

[MIT](LICENSE)
