"""Tests for UI-07 opt-in Bull/Bear LLM synthesis with FOUND-04 backtest guard (04-02 plan).

CRITICAL test: test_synthesis_skipped_in_backtest_mode asserts zero Anthropic API
calls when backtest_mode=True. This prevents ~$2.78/ticker cost on 3-year backtests.

Tests validate:
- Flag off by default: returns None without touching Anthropic
- FOUND-04: backtest_mode=True always returns None (zero API calls)
- Flag on + valid key + mocked client: returns LlmSynthesis with correct fields
- Prompt excludes PII: no dollar amounts, no thesis text, confidence bucketed
- Cache hit: second call same key returns cached=True without API call
- Missing SDK: returns None gracefully
- Missing API key: returns None gracefully
- API exception: returns None + warning appended
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers: minimal AggregatedSignal + AgentInput fixtures
# ---------------------------------------------------------------------------

def _make_aggregated_signal(
    ticker: str = "AAPL",
    final_signal_value: str = "BUY",
    confidence: float = 72.0,
    regime_value: str | None = "RISK_ON",
    agent_outputs: list | None = None,
) -> Any:
    """Build a minimal AggregatedSignal suitable for synthesis tests."""
    from agents.models import AgentOutput, Regime, Signal
    from engine.aggregator import AggregatedSignal

    if agent_outputs is None:
        out = AgentOutput(
            agent_name="TechnicalAgent",
            ticker=ticker,
            signal=Signal.BUY,
            confidence=72.0,
            reasoning="test",
        )
        agent_outputs = [out]

    regime = Regime(regime_value) if regime_value else None
    signal = Signal(final_signal_value)

    return AggregatedSignal(
        ticker=ticker,
        asset_type="stock",
        final_signal=signal,
        final_confidence=confidence,
        regime=regime,
        agent_signals=agent_outputs,
        reasoning="test reasoning",
    )


def _make_agent_input(backtest_mode: bool = False) -> Any:
    from agents.models import AgentInput
    return AgentInput(ticker="AAPL", asset_type="stock", backtest_mode=backtest_mode)


def _make_mock_client(response_text: str = '{"bull_case":"Bull","bear_case":"Bear","synthesis":"Synth"}') -> AsyncMock:
    """Build a minimal async Anthropic client mock."""
    mock_content = MagicMock()
    mock_content.text = response_text

    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_client = AsyncMock()
    mock_client.messages = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesis_off_by_default(monkeypatch: Any) -> None:
    """Returns None when ENABLE_LLM_SYNTHESIS is not set (default false)."""
    monkeypatch.delenv("ENABLE_LLM_SYNTHESIS", raising=False)
    # Also set API key so that's not the cause
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    from engine.llm_synthesis import run_llm_synthesis

    sig = _make_aggregated_signal()
    ai = _make_agent_input(backtest_mode=False)
    result = await run_llm_synthesis(sig, ai, client=None)
    assert result is None


@pytest.mark.asyncio
async def test_synthesis_skipped_in_backtest_mode(monkeypatch: Any) -> None:
    """CRITICAL FOUND-04: backtest_mode=True must produce ZERO Anthropic API calls.

    This is the cost-prevention test. A 3-year backtest with ENABLE_LLM_SYNTHESIS=true
    would cost ~$2.78/ticker without this guard.
    """
    monkeypatch.setenv("ENABLE_LLM_SYNTHESIS", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    from engine.llm_synthesis import run_llm_synthesis

    sig = _make_aggregated_signal()
    ai = _make_agent_input(backtest_mode=True)  # FOUND-04 flag
    mock_client = _make_mock_client()

    result = await run_llm_synthesis(sig, ai, client=mock_client)

    assert result is None, "backtest_mode=True must return None (FOUND-04)"
    assert mock_client.messages.create.call_count == 0, (
        "CRITICAL: Anthropic API must NOT be called in backtest_mode "
        f"(got {mock_client.messages.create.call_count} calls)"
    )


@pytest.mark.asyncio
async def test_synthesis_fires_when_enabled(monkeypatch: Any) -> None:
    """Returns LlmSynthesis with correct fields when flag is on and client mocked."""
    monkeypatch.setenv("ENABLE_LLM_SYNTHESIS", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    from engine.llm_synthesis import run_llm_synthesis

    sig = _make_aggregated_signal()
    ai = _make_agent_input(backtest_mode=False)
    mock_client = _make_mock_client('{"bull_case":"B","bear_case":"Bx","synthesis":"S"}')

    result = await run_llm_synthesis(sig, ai, client=mock_client)

    assert result is not None
    assert result.bull_case == "B"
    assert result.bear_case == "Bx"
    assert result.synthesis == "S"
    assert result.ticker == "AAPL"
    assert mock_client.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_prompt_excludes_pii(monkeypatch: Any) -> None:
    """Prompt must not contain dollar amounts, thesis text, or raw confidence integers."""
    monkeypatch.setenv("ENABLE_LLM_SYNTHESIS", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    from agents.models import AgentOutput, Signal
    from engine.llm_synthesis import run_llm_synthesis, _build_prompt

    # Agent with confidence=72 — should be bucketed to 70 in prompt
    out = AgentOutput(
        agent_name="TechnicalAgent",
        ticker="AAPL",
        signal=Signal.BUY,
        confidence=72.0,
        reasoning="test",
    )
    sig = _make_aggregated_signal(confidence=72.0, agent_outputs=[out])

    prompt = _build_prompt(sig)

    # Security: no dollar amounts
    assert "$" not in prompt, "Prompt must NOT contain dollar amounts"
    # PII: no thesis text
    assert "thesis" not in prompt.lower(), "Prompt must NOT contain thesis text"
    # Bucketing: raw confidence 72 → bucketed to 70
    assert "72" not in prompt, "Raw confidence 72 must be bucketed, not appear literally"
    # Verify bucketed value IS present
    assert "70" in prompt, "Bucketed confidence 70 must appear in prompt"
    # Ticker and signal should be in prompt
    assert "AAPL" in prompt
    assert "BUY" in prompt


@pytest.mark.asyncio
async def test_cache_hit(monkeypatch: Any) -> None:
    """Second call with same key returns cached=True and does NOT call the API again."""
    monkeypatch.setenv("ENABLE_LLM_SYNTHESIS", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    # Clear module-level cache between tests
    import engine.llm_synthesis as llm_mod
    llm_mod._CACHE.clear()

    from engine.llm_synthesis import run_llm_synthesis

    sig = _make_aggregated_signal(ticker="GOOG", confidence=80.0)
    ai = _make_agent_input(backtest_mode=False)
    mock_client = _make_mock_client('{"bull_case":"B","bear_case":"Bx","synthesis":"S"}')

    # First call: should hit the API
    result1 = await run_llm_synthesis(sig, ai, client=mock_client)
    assert result1 is not None
    assert result1.cached is False
    assert mock_client.messages.create.call_count == 1

    # Second call same signal/regime/confidence bucket: should return from cache
    result2 = await run_llm_synthesis(sig, ai, client=mock_client)
    assert result2 is not None
    assert result2.cached is True
    assert mock_client.messages.create.call_count == 1, (
        "Second call should return cached result without API call"
    )

    llm_mod._CACHE.clear()


@pytest.mark.asyncio
async def test_no_anthropic_sdk(monkeypatch: Any) -> None:
    """Returns None gracefully when AsyncAnthropic is None (SDK not installed)."""
    monkeypatch.setenv("ENABLE_LLM_SYNTHESIS", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    import engine.llm_synthesis as llm_mod
    original = llm_mod.AsyncAnthropic
    try:
        llm_mod.AsyncAnthropic = None  # type: ignore[assignment]
        from engine.llm_synthesis import run_llm_synthesis

        sig = _make_aggregated_signal()
        ai = _make_agent_input(backtest_mode=False)
        result = await run_llm_synthesis(sig, ai, client=None)
        assert result is None
    finally:
        llm_mod.AsyncAnthropic = original


@pytest.mark.asyncio
async def test_no_api_key(monkeypatch: Any) -> None:
    """Returns None when ANTHROPIC_API_KEY is not set."""
    monkeypatch.setenv("ENABLE_LLM_SYNTHESIS", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from engine.llm_synthesis import run_llm_synthesis

    sig = _make_aggregated_signal()
    ai = _make_agent_input(backtest_mode=False)
    result = await run_llm_synthesis(sig, ai, client=None)
    assert result is None


@pytest.mark.asyncio
async def test_api_exception_returns_none(monkeypatch: Any) -> None:
    """API exception returns None and appends warning to aggregated.warnings."""
    monkeypatch.setenv("ENABLE_LLM_SYNTHESIS", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    import engine.llm_synthesis as llm_mod
    llm_mod._CACHE.clear()

    from engine.llm_synthesis import run_llm_synthesis

    sig = _make_aggregated_signal(ticker="ERR")
    ai = _make_agent_input(backtest_mode=False)

    mock_client = AsyncMock()
    mock_client.messages = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))

    result = await run_llm_synthesis(sig, ai, client=mock_client)
    assert result is None
    assert any("boom" in w for w in sig.warnings), (
        f"Expected 'boom' in warnings, got: {sig.warnings}"
    )

    llm_mod._CACHE.clear()


@pytest.mark.asyncio
async def test_aggregated_signal_has_llm_synthesis_field() -> None:
    """AggregatedSignal dataclass has llm_synthesis field defaulting to None."""
    from engine.aggregator import AggregatedSignal
    from agents.models import Signal

    sig = AggregatedSignal(
        ticker="TEST",
        asset_type="stock",
        final_signal=Signal.HOLD,
        final_confidence=50.0,
        regime=None,
        agent_signals=[],
        reasoning="test",
    )
    assert hasattr(sig, "llm_synthesis")
    assert sig.llm_synthesis is None
