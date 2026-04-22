from __future__ import annotations

import asyncio
import logging

from agents.base import BaseAgent
from agents.crypto import CryptoAgent
from agents.fundamental import FundamentalAgent
from agents.macro import MacroAgent
from agents.models import AgentInput, AgentOutput
from agents.technical import TechnicalAgent
from data_providers.factory import get_provider
from data_providers.fred_provider import FredProvider
from data_providers.yfinance_provider import YFinanceProvider
from engine.aggregator import AggregatedSignal, SignalAggregator
from engine.dynamic_threshold import compute_dynamic_thresholds
from engine.sector import get_sector_modifier
from portfolio.models import Portfolio

_logger = logging.getLogger("investment_agent.pipeline")


class AnalysisPipeline:
    """End-to-end analysis pipeline for a single ticker.

    Orchestrates: DataProvider(s) → Agents → SignalAggregator.
    """

    def __init__(
        self,
        db_path: str = "investment_agent.db",
        use_adaptive_weights: bool = False,
    ) -> None:
        self._db_path = db_path
        self._use_adaptive_weights = use_adaptive_weights
        self._adaptive_weights = None  # Lazy-loaded on first analyze_ticker call

    async def _run_pipeline(
        self,
        ticker: str,
        asset_type: str,
        portfolio: Portfolio | None,
        aggregator: SignalAggregator,
        use_regime: bool,
        backtest_mode: bool = False,
    ) -> AggregatedSignal:
        """Core pipeline shared by analyze_ticker and analyze_ticker_custom.

        Handles: ticker mapping, agent init, parallel execution, signal
        aggregation (with optional regime detection), portfolio overlay,
        and sector modifier.
        """
        pipeline_warnings: list[str] = []
        _logger.info("Pipeline starting: %s (%s)", ticker, asset_type)

        # Map crypto tickers to yfinance format
        if asset_type in ("btc", "eth"):
            _CRYPTO_YF_MAP = {"BTC": "BTC-USD", "ETH": "ETH-USD"}
            ticker = _CRYPTO_YF_MAP.get(ticker.upper(), ticker)

        # 1. Create providers
        primary_provider = get_provider(asset_type)

        # 2. Initialize agents
        agents: list[BaseAgent] = []

        if asset_type in ("btc", "eth"):
            # Crypto: use dedicated CryptoAgent (7-factor model)
            agents.append(CryptoAgent(primary_provider))
        else:
            # Stocks: Technical + Fundamental + Macro
            agents.append(TechnicalAgent(primary_provider))

            if asset_type == "stock":
                agents.append(FundamentalAgent(primary_provider))

            # MacroAgent needs two providers; skip gracefully if FRED key unavailable
            try:
                fred_provider = FredProvider()
                vix_provider = YFinanceProvider()
                agents.append(MacroAgent(fred_provider, vix_provider))
            except Exception as exc:
                _logger.warning("MacroAgent skipped: %s", exc)
                pipeline_warnings.append(f"MacroAgent skipped: {exc}")

            # SentimentAgent — optional, requires anthropic SDK + API key
            try:
                from agents.sentiment import SentimentAgent
                from data_providers.news_provider import NewsProvider  # noqa: F811

                news_provider: NewsProvider | None = None
                try:
                    from data_providers.web_news_provider import WebNewsProvider
                    news_provider = WebNewsProvider()
                except Exception:
                    pass
                agents.append(SentimentAgent(primary_provider, news_provider=news_provider))
            except Exception as exc:
                _logger.warning("SentimentAgent skipped: %s", exc)
                pipeline_warnings.append(f"SentimentAgent skipped: {exc}")

        _logger.info("Selected agents: %s", [a.name for a in agents])

        # 3. Construct AgentInput
        agent_input = AgentInput(
            ticker=ticker,
            asset_type=asset_type,
            portfolio=portfolio,
            backtest_mode=backtest_mode,
        )

        # 4. Run agents + ticker info fetch in parallel
        async def _fetch_ticker_info() -> dict:
            """Fetch current price and key stats for report header."""
            info: dict = {}
            try:
                price = await primary_provider.get_current_price(ticker)
                info["current_price"] = price
            except Exception:
                pass
            try:
                stats = await primary_provider.get_key_stats(ticker)
                info.update(stats)
            except Exception:
                pass
            return info

        all_tasks = [agent.analyze(agent_input) for agent in agents]
        all_tasks.append(_fetch_ticker_info())  # type: ignore[arg-type]
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # Last result is ticker_info; rest are agent results
        ticker_info_result = results[-1]
        agent_results = results[:-1]

        ticker_info: dict = {}
        if isinstance(ticker_info_result, dict):
            ticker_info = ticker_info_result
        elif isinstance(ticker_info_result, Exception):
            pipeline_warnings.append(f"Ticker info fetch failed: {ticker_info_result}")

        # 5. Filter exceptions, collect valid outputs
        agent_outputs: list[AgentOutput] = []
        for i, result in enumerate(agent_results):
            if isinstance(result, Exception):
                _logger.warning("%s failed for %s: %s", agents[i].name, ticker, result)
                pipeline_warnings.append(f"{agents[i].name} failed: {result}")
            else:
                agent_outputs.append(result)

        # 6. Aggregate with optional regime-based weight switching
        regime_adjustments: dict[str, float] | None = None
        regime_info_dict: dict | None = None
        if use_regime:
            try:
                from engine.regime import RegimeDetector
                detector = RegimeDetector()
                regime_info = detector.detect(agent_outputs)
                # Only apply non-trivial adjustments (skip if all multipliers == 1.0)
                if any(v != 1.0 for v in regime_info.adjustments.values()):
                    regime_adjustments = regime_info.adjustments
                regime_info_dict = regime_info.to_dict()
            except ImportError:
                pass
            except Exception as exc:
                pipeline_warnings.append(f"Regime detection failed: {exc}")

        if regime_adjustments is not None:
            signal = aggregator.aggregate_with_regime(
                agent_outputs, ticker, asset_type,
                regime_adjustments=regime_adjustments,
            )
        else:
            signal = aggregator.aggregate(agent_outputs, ticker, asset_type)

        _logger.info(
            "Aggregation complete for %s: %s @ %.0f%% confidence",
            ticker, signal.final_signal.value, signal.final_confidence,
        )

        # Store regime info in metrics if available
        if regime_info_dict is not None:
            signal.metrics["regime_info"] = regime_info_dict

        # Attach ticker info and pipeline warnings
        signal.ticker_info = ticker_info
        signal.warnings.extend(pipeline_warnings)

        # 6b. Portfolio concentration overlay
        if portfolio is not None and ticker_info.get("current_price"):
            from engine.portfolio_overlay import compute_portfolio_impact

            sector = ticker_info.get("sector")
            impact = compute_portfolio_impact(
                ticker=ticker,
                asset_type=asset_type,
                current_price=ticker_info["current_price"],
                portfolio=portfolio,
                sector=sector,
            )
            signal.portfolio_impact = impact.to_dict()
            if impact.concentration_warning:
                signal.warnings.append(impact.concentration_warning)
            if impact.correlation_warning:
                signal.warnings.append(impact.correlation_warning)

        # 7. Apply sector rotation modifier (stocks only, not crypto)
        if asset_type not in ("btc", "eth"):
            sector = ticker_info.get("sector")
            regime_str = signal.regime.value if signal.regime else "NEUTRAL"
            modifier = get_sector_modifier(sector, regime_str)
            if modifier != 0:
                pre_confidence = signal.final_confidence
                signal.final_confidence = max(
                    30.0, min(90.0, signal.final_confidence + modifier)
                )
                signal.metrics["sector_modifier"] = modifier
                signal.metrics["sector_name"] = sector
                signal.metrics["pre_sector_confidence"] = pre_confidence

        # UI-07: opt-in Bull/Bear synthesis (skipped silently in backtest_mode per FOUND-04)
        try:
            from engine.llm_synthesis import run_llm_synthesis
            synthesis = await run_llm_synthesis(signal, agent_input)
            if synthesis is not None:
                signal.llm_synthesis = synthesis
        except Exception as exc:
            _logger.warning(
                "LLM synthesis step raised unexpectedly for %s: %s", ticker, exc
            )
            signal.warnings.append(f"LLM synthesis exception: {exc}")

        return signal

    async def analyze_ticker(
        self,
        ticker: str,
        asset_type: str,
        portfolio: Portfolio | None = None,
    ) -> AggregatedSignal:
        """Run full analysis pipeline for a single ticker.

        1. Initialize appropriate DataProvider(s).
        2. Select agents based on asset_type.
        3. Run all agents in parallel via asyncio.gather.
        4. Filter exceptions, collect valid outputs.
        5. Aggregate signals with SignalAggregator.
        6. Return AggregatedSignal (pipeline warnings merged in).
        """
        pipeline_warnings: list[str] = []

        # Build aggregator with adaptive or default weights
        if self._use_adaptive_weights and self._adaptive_weights is None:
            try:
                from engine.weight_adapter import WeightAdapter
                adapter = WeightAdapter(db_path=self._db_path)
                self._adaptive_weights = await adapter.load_weights()
            except Exception as exc:
                pipeline_warnings.append(f"Adaptive weights load failed: {exc}")

        if self._adaptive_weights is not None and self._use_adaptive_weights:
            aggregator = SignalAggregator(
                weights=self._adaptive_weights.weights,
                buy_threshold=self._adaptive_weights.buy_threshold,
                sell_threshold=self._adaptive_weights.sell_threshold,
            )
        else:
            # Dynamic thresholds: scale BUY/SELL thresholds by current VIX
            vix_current: float | None = None
            try:
                vix_provider = YFinanceProvider()
                vix_df = await vix_provider.get_price_history("^VIX", period="5d", interval="1d")
                if vix_df is not None and not vix_df.empty:
                    vix_current = float(vix_df["Close"].iloc[-1])
            except Exception:
                pass  # fall back to default thresholds
            buy_t, sell_t = compute_dynamic_thresholds(vix_current)
            aggregator = SignalAggregator(buy_threshold=buy_t, sell_threshold=sell_t)

        signal = await self._run_pipeline(
            ticker=ticker,
            asset_type=asset_type,
            portfolio=portfolio,
            aggregator=aggregator,
            use_regime=True,
        )
        signal.warnings[:0] = pipeline_warnings  # prepend any weight-load warnings
        return signal

    async def analyze_ticker_custom(
        self,
        ticker: str,
        asset_type: str,
        custom_weights: dict[str, dict[str, float]],
        portfolio: Portfolio | None = None,
    ) -> AggregatedSignal:
        """Run analysis with user-specified agent weights.

        Same flow as analyze_ticker but uses provided weights instead of
        default/adaptive weights, and skips regime detection.
        """
        aggregator = SignalAggregator(weights=custom_weights)
        return await self._run_pipeline(
            ticker=ticker,
            asset_type=asset_type,
            portfolio=portfolio,
            aggregator=aggregator,
            use_regime=False,
        )
