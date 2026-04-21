# Comparative Technology Stack: Agent Design & Signal Quality

**Project:** Investment Agent — Agent Design & Signal Quality Dimension
**Research Date:** 2026-04-21
**Mode:** Competitive gap analysis (brownfield)
**Confidence:** MEDIUM–HIGH (GitHub metrics verified; feature depth varies by source quality)

---

## Scope

This document surveys 14 active OSS projects in the investment-agent / algorithmic-trading / AI-finance space and compares them against our system on five dimensions:

1. Agent structure / LLM roles / tool use / memory / reflection
2. Signal aggregation strategy
3. Backtesting rigor
4. Risk modeling
5. Calibration and prediction-quality metrics

For each area the gap classification key is:

| Label | Meaning |
|-------|---------|
| **MUST** | High-value gap we are missing; concrete borrowable pattern exists |
| **NICE** | Incremental improvement; real value but not blocking |
| **NO** | Not worth the cost; low ROI or out of scope |

---

## OSS Project Registry

| # | Project | GitHub URL | Stars (Apr 2026) | Last Release | Domain Focus |
|---|---------|-----------|-----------------|--------------|-------------|
| 1 | ai-hedge-fund | https://github.com/virattt/ai-hedge-fund | 56.6k | Active (commits Mar 2026) | LLM multi-agent investing |
| 2 | TradingAgents | https://github.com/TauricResearch/TradingAgents | 52k | v0.2.3 Mar 2026 | LLM multi-agent trading |
| 3 | OpenBB | https://github.com/OpenBB-finance/OpenBB | 65.9k | Active 2026 | Financial data platform + AI agents |
| 4 | qlib (Microsoft) | https://github.com/microsoft/qlib | 41.1k | v0.9.7 Aug 2025 | Quant ML / factor research |
| 5 | FinRL | https://github.com/AI4Finance-Foundation/FinRL | 14.8k | v0.3.8 Mar 2026 | Deep RL trading |
| 6 | FinGPT | https://github.com/AI4Finance-Foundation/FinGPT | 19.7k | Active 2025 | Financial LLM fine-tuning |
| 7 | freqtrade | https://github.com/freqtrade/freqtrade | 49.1k | Active 2026 | Crypto algo trading + FreqAI |
| 8 | nautilus_trader | https://github.com/nautechsystems/nautilus_trader | 22.1k | v1.208.0 Apr 2026 | Production trading engine (Rust/Python) |
| 9 | vectorbt | https://github.com/polakowo/vectorbt | 7.2k | Active (master) | Vectorized backtesting + portfolio |
| 10 | jesse | https://github.com/jesse-ai/jesse | 7.7k | Active 2025 | Crypto algo trading + Monte Carlo |
| 11 | zipline-reloaded | https://github.com/stefan-jansen/zipline-reloaded | 1.7k | v3.1.1 Jul 2025 | Event-driven equity backtesting |
| 12 | lumibot | https://github.com/Lumiwealth/lumibot | 1.4k | v4.5.1 Apr 2026 | AI agent backtesting + live trading |
| 13 | Hummingbot | https://github.com/hummingbot/hummingbot | 18.2k | v2.13.0 Mar 2026 | Crypto market-making bots |
| 14 | QuantStats | https://github.com/ranaroussi/quantstats | Active 2025 | Portfolio analytics | Risk/performance metrics library |

**Additional academic / research frameworks reviewed (not full OSS projects):**
- MarketSenseAI (arxiv:2502.00415) — 5-agent RAG+LLM architecture; 125.9% cumulative return on S&P 100 (2023–2024) vs 73.5% index
- HedgeAgents (arxiv:2502.13165) — balanced-aware multi-agent system
- FinRL-X / FinRL-Trading (AI4Finance-Foundation/FinRL-Trading) — next-gen modular infrastructure for quantitative trading

---

## Dimension 1: Agent Structure / LLM Roles / Tool Use / Memory / Reflection

### How OSS Projects Do It

**ai-hedge-fund (56.6k stars):**
Uses LangGraph for agent orchestration. 19 agents total: 14 persona agents modeling legendary investors (Buffett, Munger, Lynch, Damodaran, etc.), 4 analysis agents (Valuation, Sentiment, Fundamentals, Technicals), and 2 operational agents (Risk Manager, Portfolio Manager). Each persona agent is an LLM instance with a system prompt encoding that investor's philosophy. Signal aggregation: portfolio manager LLM agent reads all analyst signals and produces a final weighted decision via natural language. No formal memory or reflection loop documented in the public repo (`src/backtester.py`). No tool-use framework beyond LangGraph node routing. Educational POC only; no production backtesting rigor.

**TradingAgents (52k stars):**
Built on LangGraph. Five-phase sequential pipeline: Analyst Team (4 concurrent: Fundamentals, Sentiment, News, Technical) → Research Team (Bull Researcher + Bear Researcher in structured debate) → Trader Agent → Risk Management Team → Portfolio Manager. The Bull/Bear debate is the key architectural differentiator: two agents argue opposing positions before the Trader synthesizes. Supports 13+ LLM providers (OpenAI, Anthropic, Google, xAI, Ollama). No documented memory or reflection mechanism in the public README as of v0.2.3. No quantitative backtesting rigor (LLM output, not numerical signals).

**OpenBB + openbb-agents:**
OpenBB itself is a data platform ("connect once, consume everywhere") exposing market data via MCP servers, REST APIs, Python SDK. The experimental openbb-agents project (https://github.com/OpenBB-finance/openbb-agents) uses LLMs with function calling to autonomously query OpenBB data and answer financial research questions. No multi-agent debate or reflection; single LLM with tool access to a rich data layer.

**qlib (41.1k stars):**
Not LLM-agent-based; factor/ML model pipeline. RD-Agent integration (LLM-driven automated factor mining and code generation). Agents here are ML model training loops, not LLM personas. The RD-Agent extension (https://github.com/microsoft/RD-Agent) uses LLMs to autonomously propose, implement, and evaluate new alpha factors. This is "LLM as research loop" rather than "LLM as analyst persona."

**FreqAI (freqtrade):**
ML signal generation within the Freqtrade strategy framework. Models are retrained on rolling windows (adaptive retraining). Supports classification and regression pipelines. No LLM or multi-agent design; purely ML pipeline feeding into strategy execution logic. Signal aggregation via user-defined strategy combining ML predictions with technical indicators.

**MarketSenseAI (research):**
Five specialized agents (News, Fundamentals, Dynamics, Macroeconomics, Signal Generation). Final signal agent uses CoT reasoning to fuse all other agents' outputs into a Buy/Hold/Sell decision with written rationale. RAG integration over SEC filings and earnings calls. S&P 100 backtest 2023–2024: +125.9% vs +73.5% index. This is the closest external analogue to our architecture.

### What We Do Today

- 6 agents: Technical, Fundamental, Macro, Crypto, Sentiment, Summary (`agents/`)
- No LLM personas; each agent runs deterministic Python logic (pandas_ta indicators, fundamental ratios, VIX normalization, etc.)
- Sentiment agent optionally calls Claude API for news interpretation (`agents/sentiment.py`)
- No structured debate between agents; no bull/bear researcher layer
- No formal memory: each analysis is stateless (no agent sees its own history or corrects itself)
- No reflection loop: agents do not critique each other's outputs
- No tool-use framework (agents call data providers directly, not via LangGraph/CrewAI/AutoGen)

### Gap Analysis

| Gap | Classification | Rationale |
|-----|---------------|-----------|
| Bull/Bear researcher debate layer (TradingAgents pattern) | **MUST** | Forces explicit consideration of downside before aggregation. Our aggregator averages signals; a debate layer catches cases where one strongly-negative agent is drowned out by four neutral ones. Borrowable: add a `ResearchSynthesizer` step that runs a structured pro/con prompt over all agent outputs before producing final signal. Cost: 1 LLM call per analysis. Integration surface: `engine/pipeline.py` post-gather, pre-aggregation. |
| Agent memory / historical context | **NICE** | Agents that remember their last 5 signals for a ticker can detect their own drift. Low priority vs other gaps but enables "self-aware" confidence dampening. Integration surface: pass signal history from `tracking/store.py` back into agent context. No new infrastructure needed. |
| LangGraph / structured agent orchestration | **NICE** | LangGraph is mature (used by TradingAgents and ai-hedge-fund) but adds a dependency. Our current `asyncio.gather()` pipeline is simpler and faster for our deterministic Python agents. Worth evaluating only if we add true LLM-persona agents. |
| LLM persona agents (Buffett, Munger style) | **NO** | Persona prompting is entertaining but not reliably calibrated. Our deterministic agent logic is more predictable and testable. Educational novelty, not signal quality. |
| RAG over SEC filings / earnings calls | **NICE** | MarketSenseAI shows RAG materially improves fundamental analysis. We have no SEC filing ingestion. Would require a document store (Chroma, FAISS). Not blocking for this milestone. |

**Recommended borrowable pattern — Bull/Bear synthesis step:**
```python
# engine/pipeline.py (new step after asyncio.gather())
async def _run_synthesis(agent_outputs: list[AgentOutput], ticker: str) -> SynthesisOutput:
    bull_case = [a for a in agent_outputs if a.signal.value > 0.5]
    bear_case = [a for a in agent_outputs if a.signal.value < -0.5]
    prompt = f"Bull signals: {bull_case}\nBear signals: {bear_case}\nSynthesize..."
    return await llm_client.complete(prompt)
```
Integration: opt-in via `ENABLE_LLM_SYNTHESIS=true` env flag; falls back to current weighted average if disabled.

---

## Dimension 2: Signal Aggregation Strategy

### How OSS Projects Do It

**ai-hedge-fund:**
Portfolio Manager LLM agent reads all analyst signals in natural language and produces a final Buy/Hold/Sell. No documented numerical weighting; purely LLM-driven. No regime conditioning. No ensemble formalism.

**TradingAgents:**
Sequential: Analyst team outputs → Researcher debate → Trader decision. No documented numerical weighting formula. LLM-as-judge pattern at each step (the next agent in the pipeline judges the previous). No adaptive weights or regime switching.

**qlib:**
Factor model paradigm. Alpha factors (IC-based) are combined via mean-rank or linear weighting. Portfolio construction via optimizer (mean-variance or risk-budget). No LLM in the signal path. Regime conditioning via DDG-DA (domain generalization for concept drift). Rolling retraining for non-stationarity.

**FreqAI:**
ML model outputs a prediction probability; strategy rules convert it to signal using configurable thresholds. Community contributions show dynamic weighting (e.g., LSTM + aggregate scoring system). Models retrained on sliding windows to handle regime shifts.

**vectorbt:**
Signal combination is user-defined; vectorbt provides the evaluation harness not the combination logic. Walk-forward optimization to select weights. Supports multi-signal portfolio simulation.

**jesse:**
Monte Carlo mode shuffles trade order to test signal robustness. ML pipeline (scikit-learn) for labeling. No ensemble weighting framework built in; user-defined strategy logic.

**MarketSenseAI:**
CoT fusion: final signal agent writes a reasoning chain over all other agents' outputs. No numerical ensemble; LLM reasoning is the aggregation function.

**TauricResearch TradingAgents:**
Bull/Bear researcher outputs feed the Trader agent, which produces a signal with confidence. Risk Management then applies a kill-switch / position-size modifier. Multi-stage LLM pipeline acts as sequential Bayesian update (informally).

### What We Do Today

- Weighted average: `∑(agent_signal × weight) / ∑weights` (`engine/aggregator.py`)
- Bidirectional threshold grid search for BUY and SELL thresholds independently (`engine/weight_adapter.py`)
- Regime-based weight switching via MacroAgent regime output
- Adaptive weights: historical accuracy tracking updates agent weights (`engine/weight_adapter.py`)
- Relative VIX normalization (ratio to 20-day SMA) as regime signal (`agents/macro.py`)
- Sector-relative P/E for fundamental scoring (`agents/fundamental.py`)
- Context-aware RSI (trend direction modulates score) (`agents/technical.py`)

### Gap Analysis

| Gap | Classification | Rationale |
|-----|---------------|-----------|
| LLM-as-judge synthesis (TradingAgents / MarketSenseAI) | **MUST** | Our weighted average can be dominated by volume (4 agents say HOLD weakly, 1 says SELL strongly → still HOLD). An LLM synthesis step reads the reasoning, not just the numbers. Catches qualitative risk that the aggregator misses. Integration: post-aggregation, pre-final-signal; opt-in. |
| IC/ICIR-based weight optimization (qlib pattern) | **MUST** | Our weight adapter uses historical prediction accuracy (hit rate). Qlib uses Information Coefficient (correlation between predicted and realized returns). IC/ICIR is a more rigorous and industry-standard signal quality metric. IC = Pearson correlation of predicted rank vs actual rank return over rolling window. Already have `tracking/tracker.py` with accuracy data; extend to compute rolling IC per agent. |
| Confidence-weighted ensemble with uncertainty estimates | **NICE** | Each agent already returns `confidence` (0–1). We use it in final output but not in the aggregation weighting. Multiply `agent_signal × confidence × weight` rather than just `signal × weight`. Small change with potential signal quality improvement. Integration: `engine/aggregator.py` lines 150-180. |
| Bayesian updating of agent weights | **NICE** | Replace static adaptive weights with a Bayesian posterior over agent reliability. Requires a prior + likelihood function. More principled than grid search but adds complexity. Defer unless IC-based weights prove insufficient. |
| Reinforcement learning for weight optimization (FinRL pattern) | **NO** | RL requires a simulator and extensive training data; our signal-level RL would need 5+ years of labeled signals per agent. Cost >> benefit for a 6-agent system with relatively sparse trading signals. |

**Recommended borrowable pattern — rolling IC per agent:**
```python
# tracking/tracker.py (extend existing)
def compute_rolling_ic(agent_name: str, window_days: int = 60) -> float:
    """IC = Pearson correlation of agent signal rank vs forward return rank."""
    signals = store.get_signals(agent_name, lookback_days=window_days)
    forward_returns = store.get_forward_returns(signals)
    return scipy.stats.pearsonr(
        rankdata(signals['signal_value']),
        rankdata(forward_returns['return_5d'])
    )[0]
```
Then `weight_adapter.py` uses `max(0, ic)` to gate weights (negative IC agent gets zero weight).

---

## Dimension 3: Backtesting Rigor

### How OSS Projects Do It

**qlib (41.1k stars) — GOLD STANDARD:**
- Point-in-time database prevents look-ahead bias (fundamentals are stored at the date they were first published, not restated values)
- Rolling walk-forward with expanding windows
- Information Coefficient (IC), ICIR, Rank IC as primary backtest quality metrics
- Transaction costs modeled (`qlib/backtest/exchange.py`)
- Benchmark comparison built-in (CSI 500, NASDAQ 100)
- Purged cross-validation support (purge + embargo to prevent data leakage)
- Concept drift handling via DDG-DA meta-learning

**freqtrade (49.1k stars):**
- Walk-forward analysis built into FreqAI retraining cycle
- Transaction fees included by default (exchange fee tables)
- Slippage modeling configurable
- Hyperopt for parameter optimization with configurable loss functions
- No documented survivorship bias handling

**vectorbt (7.2k stars):**
- Walk-forward optimization in the open-source version (`examples/WalkForwardOptimization.ipynb`)
- vectorbt PRO adds: block bootstrap, random windows, Monte Carlo trade shuffle, noise injection
- Performance metrics via QuantStats integration
- No point-in-time data handling (user's responsibility)

**jesse (7.7k stars):**
- Monte Carlo: two modes — trade-order shuffle and candles-based resampling
- No look-ahead bias by design (event-driven execution model)
- No documented survivorship bias handling
- No walk-forward optimization (hyperparameter search via separate Optuna-based tool)

**zipline-reloaded (1.7k stars):**
- Event-driven, look-ahead bias prevention enforced architecturally (pipeline API separates data access from strategy)
- Quantopian-era focus on equity factor backtesting
- No built-in walk-forward; user-defined rolling windows
- No documented Monte Carlo or block bootstrap

**nautilus_trader (22.1k stars):**
- Nanosecond-resolution event-driven backtester (Rust core)
- Identical strategy code in backtest and live
- Transaction costs and slippage configurable
- Multi-venue, multi-instrument support
- No documented walk-forward or Monte Carlo risk analysis

**ai-hedge-fund / TradingAgents:**
- Minimal backtesting: simple date-range replay with Sharpe + cumulative return output
- No transaction costs, no slippage, no walk-forward, no regime conditioning
- LLM token cost means "backtesting" 5 years of daily signals is expensive (≈365×5×LLM calls)

### What We Do Today

- Block-bootstrap Monte Carlo: 10,000 iterations, block_size=5, preserves volatility clustering (`engine/monte_carlo.py`)
- Regime context applied to backtesting signals
- No walk-forward testing (single in-sample backtest period)
- No purged cross-validation
- No transaction costs modeled in backtester
- No slippage model
- No point-in-time fundamental data (yfinance returns current/restated values — see CONCERNS.md "Point-in-time fundamental data")
- No survivorship bias handling (yfinance only returns currently-listed tickers)

### Gap Analysis

| Gap | Classification | Rationale |
|-----|---------------|-----------|
| Walk-forward backtesting | **MUST** | Single-period backtesting is insufficient for validating regime-aware signals. Walk-forward tests whether adaptive weights actually adapt well on unseen periods. Implementation: rolling `(train_start, train_end, test_start, test_end)` windows in the backtest runner. Existing `backtesting/` module can be extended. No new dependencies. |
| Transaction costs in backtester | **MUST** | Without costs, backtests overstate returns. Commission (0.05–0.10% per trade) and bid-ask spread should be deducted. Simple to add: multiply `return_before_costs × (1 - cost_per_trade)^n_trades`. |
| Block bootstrap block-size optimization (variable by asset class) | **MUST** | Our block_size=5 is hardcoded (see CONCERNS.md). Literature suggests equities: 10–15 days, crypto: 3–5 days. Add `block_size: int | None = None` parameter; if None, use Patton-Politis-White automatic block-size selection (available in `arch` library). |
| Purged cross-validation | **NICE** | Prevents leakage in ML-adjacent signal evaluation. Our adaptive weight training is not ML-based so the leakage risk is lower, but adding a purge gap between train/test periods for walk-forward would improve rigor. mlfinlab library implements this. |
| Point-in-time fundamental data | **NICE** | As noted in CONCERNS.md, FundamentalAgent uses restated yfinance data in backtests. Fixes require a paid data provider (FMP, Compustat). Defer; flag backtest results as having this bias. |
| Slippage model | **NICE** | Market impact model (e.g., linear slippage proportional to position size). Matters more for execution tools; we are signal-only, so a simple fixed-rate slippage assumption suffices. |
| Survivorship bias handling | **NICE** | yfinance only includes currently-listed symbols. Adds survivorship bias to backtests (all tickers "survived" to today). Fixing requires a historical constituent list (e.g., CRSP, or a manual S&P 500 history file). Feasible with free data but non-trivial. |

**Recommended integration: walk-forward scaffold**
```python
# backtesting/walk_forward.py (new file)
def walk_forward_windows(
    start: date, end: date,
    train_months: int = 12,
    test_months: int = 3,
    step_months: int = 3,
) -> list[tuple[date, date, date, date]]:
    """Yield (train_start, train_end, test_start, test_end) tuples."""
    ...
```
The existing `backtesting/` module runs each window independently; results are aggregated and plotted as an equity curve.

---

## Dimension 4: Risk Modeling

### How OSS Projects Do It

**qlib:**
Portfolio optimization with risk budget (covariance matrix). No Monte Carlo in the signal layer; risk is handled in the portfolio construction layer. Supports mean-variance, risk parity.

**QuantStats (library, widely used):**
- Conditional VaR (CVaR / Expected Shortfall)
- Historical VaR (parametric and empirical)
- Maximum drawdown, Ulcer Index
- Monte Carlo simulations (random draw, not block bootstrap)
- Runs thousands of scenarios; output includes probability-weighted return distributions
- Actively maintained (pyfolio is deprecated)
- Drop-in integration with any returns series

**vectorbt PRO:**
Block bootstrap, Monte Carlo trade shuffle, noise injection. Community edition (7.2k stars) has walk-forward optimization example.

**jesse (7.7k stars):**
Monte Carlo: trade-order shuffle (tests whether trade sequencing drove results) + candles-based (tests market condition sensitivity). Two complementary modes provide robustness check.

**nautilus_trader:**
Rust-core execution with nanosecond precision; no built-in portfolio-level VaR or Monte Carlo documented.

**freqtrade:**
No built-in risk modeling beyond per-strategy stop-loss and position sizing. FreqAI ML model gives probability estimates but no VaR/CVaR.

**ai-hedge-fund / TradingAgents:**
Risk Manager agent applies qualitative position-size constraints (e.g., "do not exceed X% in a single position"). No quantitative risk model.

### What We Do Today

- Block-bootstrap Monte Carlo: 10,000 iterations preserving volatility clustering (`engine/monte_carlo.py`)
- No VaR or CVaR computation
- No CVaR on portfolio level (only single-ticker Monte Carlo)
- Drawdown tracking in `engine/analytics.py` (portfolio snapshots)
- No portfolio-level risk aggregation (correlations between positions not modeled)
- Block size is hardcoded (5 days); see CONCERNS.md

### Gap Analysis

| Gap | Classification | Rationale |
|-----|---------------|-----------|
| CVaR / Expected Shortfall | **MUST** | VaR tells us the 95th-percentile loss; CVaR tells us the expected loss *given* we're in the tail. CVaR is superior for tail risk. QuantStats computes it in one line. Integration: add `quantstats` as optional dependency; call `qs.stats.cvar(returns)` in `engine/analytics.py` and surface in the API response. |
| Portfolio-level risk aggregation (correlation-aware) | **MUST** | Our Monte Carlo runs per-ticker. A portfolio of correlated positions can have amplified tail risk that per-ticker Monte Carlo misses. Need a covariance matrix across holdings and portfolio-level VaR. Integration: `engine/analytics.py` — compute pairwise return correlations for held positions; run portfolio-level simulation. |
| Jesse-style dual Monte Carlo (trade shuffle + candles) | **NICE** | We use candles-based block bootstrap. Adding trade-order shuffle as a second check would identify whether signal timing (not just market conditions) drives results. Conceptually simple to add to `engine/monte_carlo.py`. |
| Dynamic block-size selection (Patton-Politis-White) | **MUST** | See CONCERNS.md: block_size=5 is hard-coded. The `arch` library provides `optimal_block_length()` for automatic selection. Install: `pip install arch`. One function call replaces the hard-coded constant. High confidence fix, low effort. |
| QuantStats integration for tearsheets | **NICE** | QuantStats generates Sharpe, Sortino, Calmar, CVaR, Max DD, drawdown histogram, and monthly returns heatmap in a single call. Replaces our manual `engine/analytics.py` metric calculations. Import: `import quantstats as qs; qs.extend_pandas()`. |
| Regime-conditioned VaR | **NICE** | Run separate VaR estimates per detected regime (bull/bear/high-vol). Our regime detector already classifies regimes; conditioning VaR on regime would be more informative than a single unconditional estimate. |

**Recommended immediate integration: CVaR via QuantStats**
```python
# engine/analytics.py (add to existing analytics)
import quantstats as qs
def compute_risk_metrics(returns: pd.Series) -> dict:
    return {
        "cvar_95": qs.stats.cvar(returns, sigma=1.65),
        "var_95": qs.stats.value_at_risk(returns),
        "max_drawdown": qs.stats.max_drawdown(returns),
        "sharpe": qs.stats.sharpe(returns),
        "sortino": qs.stats.sortino(returns),
        "calmar": qs.stats.calmar(returns),
    }
```
This replaces or augments the existing analytics; no schema change required initially (add as new `risk_metrics` field in API response).

**Recommended: `arch` library for dynamic block size**
```python
# engine/monte_carlo.py
from arch.bootstrap import optimal_block_length
def _select_block_size(returns: np.ndarray) -> int:
    res = optimal_block_length(returns)
    return max(3, int(res['stationary'].iloc[0]))
```
Resolves the CONCERNS.md residual risk around hardcoded block_size=5.

---

## Dimension 5: Calibration and Prediction-Quality Metrics

### How OSS Projects Do It

**qlib:**
Information Coefficient (IC) and ICIR (IC's Sharpe ratio) are primary signal quality metrics. IC = Pearson correlation of predicted rank vs actual forward return rank over a rolling window. ICIR = mean(IC) / std(IC) — measures consistency. Rank IC (Spearman) is more robust to outliers. These are industry-standard metrics for alpha factor evaluation.

**freqtrade / FreqAI:**
Custom loss functions for hyperopt (Sharpe, Sortino, profit factor, custom). ML calibration: scikit-learn `CalibratedClassifierCV` can be applied to FreqAI classifiers. No built-in Brier score or log-loss reporting; user-defined.

**jesse:**
ML pipeline generates "a full report with feature importance, calibration, and metrics" when training — calibration output is documented but details are sparse.

**vectorbt PRO:**
No built-in prediction calibration; focused on portfolio simulation. Users bring their own signal scores.

**ai-hedge-fund / TradingAgents:**
No calibration. LLM outputs Buy/Hold/Sell with no probability estimate that could be calibrated. Portfolio manager produces confidence as free text ("high confidence" etc.) not a numeric probability.

**Academic / research context (2025):**
Literature consensus (EMNLP 2025, ACL 2025 proceedings) on LLM financial agent evaluation:
- Brier score = proper scoring rule for binary outcomes (predicted probability vs 0/1 outcome)
- Log-loss = training loss for calibrated ML classifiers
- Calibration plots (reliability diagrams): predicted probability percentiles vs actual win rates
- Sharpe/Sortino/Calmar + hit rate at realistic rebalancing frequencies are the economically grounded metrics
- IC/ICIR are the signal quality metrics for factor models

### What We Do Today

- Signal accuracy tracking: compare historical Buy/Hold/Sell signals vs actual price moves at N days forward (`tracking/tracker.py`)
- No Brier score
- No log-loss
- No calibration plot / reliability diagram
- No IC/ICIR computation
- Agent confidence (0–1) is self-reported by each agent, not calibrated against outcomes
- Weight adapter uses raw hit rate (accuracy) not IC

### Gap Analysis

| Gap | Classification | Rationale |
|-----|---------------|-----------|
| Rolling IC/ICIR per agent | **MUST** | IC is the correct metric for evaluating signal quality in a factor-model context. Hit rate (what we use) treats all correct predictions equally; IC weights by magnitude of prediction vs magnitude of outcome. An agent with 55% accuracy but high-magnitude-correct predictions ranks higher on IC. Already have the raw data in `tracking/tracker.py`. Add `compute_rolling_ic()` and expose in analytics API. |
| Brier score for confidence calibration | **MUST** | Our agents return a `confidence` float (0–1). If confidence=0.8 is declared but the agent is right only 60% of the time when it says 0.8, that confidence is miscalibrated. Brier score = mean((predicted_confidence - outcome)^2). Low implementation effort; high diagnostic value. Integration: `tracking/tracker.py` — add `compute_brier_score(agent_name)` using signal history and forward returns. |
| Calibration plot (reliability diagram) | **NICE** | Visual check: bin confidence scores into deciles, compute actual win rate per bin. If the plot is diagonal → well-calibrated. If it bows → over-confident. Generate as a Plotly chart in the analytics section of the dashboard. Integration surface: `engine/analytics.py` + frontend charting component. |
| Platt scaling / isotonic regression for confidence recalibration | **NICE** | If agents are systematically over/under-confident, apply sklearn's `CalibratedClassifierCV` or `isotonic_regression` to recalibrate outputs post-hoc. Requires training data (signal history). Feasible after Brier score confirms miscalibration exists. |
| Log-loss for multi-class signal output | **NO** | Our signals are continuous (-1 to 1), not class probabilities. Log-loss applies to the ML classification context (FreqAI); our deterministic agents don't produce a log-likelihood. Not applicable. |

**Recommended implementation: Brier score + IC in tracker**
```python
# tracking/tracker.py (extend existing)
def compute_brier_score(agent_name: str, horizon_days: int = 5) -> float:
    """Brier score = mean((confidence - binary_outcome)^2)."""
    rows = store.get_agent_signals_with_outcomes(agent_name, horizon_days)
    return float(np.mean((rows['confidence'] - rows['outcome_binary']) ** 2))

def compute_rolling_ic(agent_name: str, window_days: int = 60) -> float:
    """IC = Pearson corr of signal_value rank vs forward_return rank."""
    rows = store.get_agent_signals_with_returns(agent_name, window_days)
    ic, _ = scipy.stats.pearsonr(rankdata(rows['signal_value']), rankdata(rows['forward_return_5d']))
    return ic
```
These two functions + a new `/api/v1/analytics/calibration` endpoint expose calibration data for the dashboard.

---

## Cross-Cutting Borrowable Patterns Summary

### Must-Borrow (Priority Order)

| # | Pattern | Source Project | Our Integration Surface | Effort |
|---|---------|---------------|------------------------|--------|
| 1 | Dynamic block-size selection via `arch.optimal_block_length()` | Research consensus | `engine/monte_carlo.py` — replace hardcoded `block_size=5` | Low (1 function call) |
| 2 | CVaR / Expected Shortfall via QuantStats | QuantStats library | `engine/analytics.py` — add `compute_risk_metrics()` | Low (1 dependency) |
| 3 | Transaction costs in backtester | qlib, freqtrade | `backtesting/` — add `cost_per_trade` parameter | Low–Medium |
| 4 | Rolling IC/ICIR per agent | qlib | `tracking/tracker.py` — extend existing accuracy tracking | Medium |
| 5 | Brier score for confidence calibration | Academic / research | `tracking/tracker.py` — extend alongside IC | Medium |
| 6 | Walk-forward backtesting scaffold | freqtrade, vectorbt | `backtesting/walk_forward.py` (new file) | Medium |
| 7 | Portfolio-level VaR (correlation-aware) | qlib / QuantStats | `engine/analytics.py` — covariance matrix across held positions | Medium–High |
| 8 | LLM synthesis / Bull-Bear step | TradingAgents, MarketSenseAI | `engine/pipeline.py` — opt-in post-gather step | Medium (opt-in) |

### Nice-to-Borrow (Defer to Later Milestones)

| Pattern | Source Project | Why Defer |
|---------|---------------|-----------|
| Agent memory / historical context | TradingAgents | Adds state complexity; current stateless design is simpler to test |
| Calibration plot (reliability diagram) | Research | Dashboard work; depends on Brier score being implemented first |
| Jesse dual Monte Carlo (trade shuffle) | jesse | Our block bootstrap already covers scenario diversity; second mode is incremental |
| QuantStats tearsheet integration | QuantStats | Nice visual; depends on analytics extension above |
| Regime-conditioned VaR | Research | Requires regime-tagged return series; depends on walk-forward first |
| RAG over SEC filings | MarketSenseAI | Needs document store; significant infrastructure; out of scope this milestone |
| Platt scaling / isotonic calibration | Research | Depends on Brier score data accumulation (months of history) |
| IC/ICIR-based dynamic weight adapter | qlib | Depends on IC computation being stable; upgrade from hit-rate weights |

### Not Worth Borrowing

| Pattern | Source Project | Rationale |
|---------|---------------|-----------|
| LLM persona agents (investor personas) | ai-hedge-fund | Not calibrated; our deterministic agents are more testable and reproducible |
| RL for weight optimization | FinRL | Requires a simulator and years of labeled signal data; cost >> benefit |
| LangGraph orchestration (without LLM agents) | TradingAgents | Adds dependency overhead; our asyncio.gather() pipeline is simpler for deterministic agents |
| Log-loss metric | freqtrade / ML context | Not applicable to our continuous-signal deterministic agent outputs |
| Nanosecond-resolution backtesting | nautilus_trader | We are signal-level (daily), not tick-level; Rust-core overkill for our use case |
| Hummingbot market-making strategies | Hummingbot | Market-making is explicitly out of scope; different problem domain |

---

## Library Recommendations

| Library | Version | Purpose | Integration Surface | Why This Library |
|---------|---------|---------|---------------------|-----------------|
| `quantstats` | 0.0.62+ | CVaR, VaR, Sharpe, Sortino, Calmar, drawdown analytics, tearsheets | `engine/analytics.py` | Actively maintained; replaces deprecated pyfolio; one-line metric generation; MIT license |
| `arch` | 6.x | Optimal block-length selection for block bootstrap (`optimal_block_length()`) | `engine/monte_carlo.py` | Research-grade GARCH/bootstrap library; Patton-Politis-White method is the academic standard for block-size selection |
| `scipy.stats` | already in ecosystem | IC computation via `pearsonr`, `spearmanr` | `tracking/tracker.py` | Already available via numpy/scipy; no new dependency |
| `scikit-learn` (calibration module) | already common | `CalibratedClassifierCV`, `calibration_curve` for reliability diagrams | `tracking/tracker.py` (future) | Standard ML calibration; only needed after Brier score confirms miscalibration |
| `mlfinlab` | 0.15+ | Purged cross-validation, combinatorial purged CV, fractional differentiation | `backtesting/walk_forward.py` | The Hudson & Thames implementation of Marcos Lopez de Prado's ML for Finance methods; implements CPCV |

**Note on mlfinlab:** The library is maintained but not heavily star'd; the purged CV implementation is the specific feature needed, which could alternatively be implemented from scratch using Lopez de Prado's open-source code (https://github.com/hudson-and-thames/mlfinlab). Confidence: MEDIUM.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Risk metrics library | QuantStats | pyfolio | pyfolio is deprecated; QuantStats is its maintained successor with Monte Carlo addition |
| Block bootstrap | arch.optimal_block_length | Fixed block_size | Addresses CONCERNS.md residual risk; literature standard |
| Walk-forward | Custom scaffold in `backtesting/` | Adopt vectorbt / Zipline | Our backtest is agent-pipeline-based, not pure price-series-based; vectorbt/Zipline would require porting the agent architecture |
| Signal quality metric | IC/ICIR | Hit rate (current) | IC is standard for factor models; hit rate treats all correct predictions equally |
| Calibration | Brier score | Log-loss | Brier score applies to binary outcomes (up/down); log-loss needs class probabilities |
| LLM orchestration | Direct asyncio + optional LLM synthesis | LangGraph | LangGraph is appropriate when all agents are LLM-powered; our agents are mostly deterministic Python |

---

## Sources

- ai-hedge-fund: https://github.com/virattt/ai-hedge-fund (56.6k stars, fetched Apr 2026)
- TradingAgents: https://github.com/TauricResearch/TradingAgents (52k stars, v0.2.3 Mar 2026)
- OpenBB: https://github.com/OpenBB-finance/OpenBB (65.9k stars, fetched Apr 2026)
- OpenBB Agents (experimental): https://github.com/OpenBB-finance/openbb-agents
- qlib: https://github.com/microsoft/qlib (41.1k stars, v0.9.7 Aug 2025)
- FinRL: https://github.com/AI4Finance-Foundation/FinRL (14.8k stars, v0.3.8 Mar 2026)
- FinGPT: https://github.com/AI4Finance-Foundation/FinGPT (19.7k stars, fetched Apr 2026)
- freqtrade: https://github.com/freqtrade/freqtrade (49.1k stars, fetched Apr 2026)
- nautilus_trader: https://github.com/nautechsystems/nautilus_trader (22.1k stars, v1.208.0 Apr 2026)
- vectorbt: https://github.com/polakowo/vectorbt (7.2k stars, fetched Apr 2026)
- jesse: https://github.com/jesse-ai/jesse (7.7k stars, fetched Apr 2026)
- zipline-reloaded: https://github.com/stefan-jansen/zipline-reloaded (1.7k stars, v3.1.1 Jul 2025)
- lumibot: https://github.com/Lumiwealth/lumibot (1.4k stars, v4.5.1 Apr 2026)
- Hummingbot: https://github.com/hummingbot/hummingbot (18.2k stars, v2.13.0 Mar 2026)
- QuantStats: https://github.com/ranaroussi/quantstats (fetched Apr 2026)
- MarketSenseAI 2.0: https://arxiv.org/html/2502.00415v2
- HedgeAgents: https://arxiv.org/html/2502.13165v1
- TradingAgents paper: https://arxiv.org/abs/2412.20138
- Block bootstrap literature: https://portfoliooptimizer.io/blog/bootstrap-simulation-with-portfolio-optimizer-usage-for-financial-planning/
- Purged CV: https://en.wikipedia.org/wiki/Purged_cross-validation
- LLM calibration: https://simplefunctions.dev/opinions/brier-vs-log-vs-quadratic
- LLM agents in finance survey: https://pmc.ncbi.nlm.nih.gov/articles/PMC12421730/
- qlib IC/ICIR documentation: https://vadim.blog/qlib-ai-quant-workflow-scoreic
- Regime detection review: https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/

---

*Research date: 2026-04-21 | Confidence: MEDIUM–HIGH | Covers 14 OSS projects + 3 research papers*
