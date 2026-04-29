from __future__ import annotations
from unittest.mock import AsyncMock
import pytest
from agents.fundamental import FundamentalAgent
from agents.models import AgentInput, Signal


@pytest.mark.asyncio
async def test_fundamental_agent_backtest_mode_default_unchanged() -> None:
    """Pitfall 1 tripwire — FOUND-04 contract regression.

    AgentInput(backtest_mode=True) MUST return HOLD with data_completeness=0.0
    and MUST NOT invoke any provider method. This test is intentionally pinned
    to the v1.1 default contract; it should fail loudly if a future change
    accidentally lifts the FOUND-04 short-circuit (Phase 8 SimFin work or
    beyond). It is a Wave 0 prerequisite — lands BEFORE any SimFin code.
    """
    provider = AsyncMock()
    agent = FundamentalAgent(provider)
    agent_input = AgentInput(
        ticker="AAPL",
        asset_type="stock",
        backtest_mode=True,
    )

    out = await agent.analyze(agent_input)

    assert out.signal == Signal.HOLD, (
        f"FOUND-04 contract violated: backtest_mode=True must return HOLD, got {out.signal}"
    )
    assert out.data_completeness == 0.0, (
        f"FOUND-04 contract violated: backtest_mode=True must yield data_completeness=0.0, "
        f"got {out.data_completeness}"
    )
    assert any(
        "backtest_mode" in w.lower() or "look-ahead" in w.lower() for w in out.warnings
    ), f"FOUND-04 warning text missing from {out.warnings}"
    provider.get_key_stats.assert_not_called()
    provider.get_financials.assert_not_called()
