from __future__ import annotations

import asyncio
from agents.base import BaseAgent
from agents.fundamental import FundamentalAgent
from agents.macro import MacroAgent
from agents.models import AgentInput, AgentOutput
from agents.technical import TechnicalAgent
from data_providers.factory import get_provider
from data_providers.fred_provider import FredProvider
from data_providers.yfinance_provider import YFinanceProvider
from engine.aggregator import AggregatedSignal, SignalAggregator
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

        # 4. Run agents in parallel
        results = await asyncio.gather(
            *[agent.analyze(agent_input) for agent in agents],
            return_exceptions=True,
        )

        # 5. Filter exceptions, collect valid outputs
        agent_outputs: list[AgentOutput] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pipeline_warnings.append(f"{agents[i].name} failed: {result}")
            else:
                agent_outputs.append(result)

        # 6. Aggregate
        aggregator = SignalAggregator()
        signal = aggregator.aggregate(agent_outputs, ticker, asset_type)

        # Merge pipeline-level warnings into the signal
        signal.warnings.extend(pipeline_warnings)

        return signal
