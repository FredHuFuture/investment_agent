from __future__ import annotations

import asyncio
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
from engine.sector import get_sector_modifier
from portfolio.models import Portfolio


class AnalysisPipeline:
    """End-to-end analysis pipeline for a single ticker.

    Orchestrates: DataProvider(s) → Agents → SignalAggregator.
    """

    def __init__(
        self,
        db_path: str = "investment_agent.db",
    ) -> None:
        # Phase 2: db_path will be used to load learned weights from
        # agent_performance table for adaptive weight tuning.
        self._db_path = db_path

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
                pipeline_warnings.append(f"MacroAgent skipped: {exc}")

        # 3. Construct AgentInput
        agent_input = AgentInput(
            ticker=ticker,
            asset_type=asset_type,
            portfolio=portfolio,
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
                pipeline_warnings.append(f"{agents[i].name} failed: {result}")
            else:
                agent_outputs.append(result)

        # 6. Aggregate
        aggregator = SignalAggregator()
        signal = aggregator.aggregate(agent_outputs, ticker, asset_type)

        # Attach ticker info and pipeline warnings
        signal.ticker_info = ticker_info
        signal.warnings.extend(pipeline_warnings)

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

        return signal
