"""Tests for Task 026: Claude Weekly Portfolio Summary (SummaryAgent).

All Claude API calls are mocked -- zero real API spending.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.database import init_db
from portfolio.manager import PortfolioManager
from agents.summary_agent import (
    PortfolioContext,
    PositionContext,
    SummaryAgent,
    SummaryResult,
    get_latest_summary,
    save_summary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_path(tmp_path):
    """Create a temp DB with schema and seed data."""
    path = str(tmp_path / "test.db")
    await init_db(path)

    mgr = PortfolioManager(path)
    await mgr.set_cash(50_000.0)
    await mgr.add_position(
        ticker="AAPL",
        asset_type="stock",
        quantity=100,
        avg_cost=150.0,
        entry_date="2025-12-01",
        thesis_text="AI growth will drive Services revenue to 30% of total",
        expected_return_pct=0.20,
        expected_hold_days=180,
        target_price=180.0,
        stop_loss=130.0,
    )
    await mgr.add_position(
        ticker="BTC",
        asset_type="btc",
        quantity=0.5,
        avg_cost=60000.0,
        entry_date="2025-11-15",
    )
    return path


def _make_context(with_thesis: bool = True) -> PortfolioContext:
    """Build a test PortfolioContext."""
    positions = [
        PositionContext(
            ticker="AAPL",
            asset_type="stock",
            quantity=100,
            avg_cost=150.0,
            current_price=165.0,
            unrealized_pnl_pct=0.10,
            holding_days=100,
            thesis_text="AI growth will drive Services revenue" if with_thesis else None,
            expected_return_pct=0.20 if with_thesis else None,
            expected_hold_days=180 if with_thesis else None,
            target_price=180.0 if with_thesis else None,
            stop_loss=130.0 if with_thesis else None,
            latest_signal="BUY",
            latest_confidence=72.0,
            week_return_pct=0.025,
        ),
        PositionContext(
            ticker="BTC",
            asset_type="btc",
            quantity=0.5,
            avg_cost=60000.0,
            current_price=67000.0,
            unrealized_pnl_pct=0.1167,
            holding_days=120,
            thesis_text=None,
            latest_signal=None,
            latest_confidence=None,
            week_return_pct=-0.01,
        ),
    ]
    return PortfolioContext(
        positions=positions,
        total_value=100_000.0,
        cash_pct=0.50,
        period="2026-03-04 to 2026-03-11",
    )


def _mock_anthropic_response(text: str = "Summary text here."):
    """Build a mock Anthropic Messages response."""
    content_block = MagicMock()
    content_block.text = text

    usage = MagicMock()
    usage.input_tokens = 1500
    usage.output_tokens = 400

    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_context(db_path):
    """Verify context gathering from DB with test fixtures."""
    context = await SummaryAgent.build_context(db_path)

    assert isinstance(context, PortfolioContext)
    assert len(context.positions) == 2
    assert context.total_value > 0
    assert context.cash_pct > 0

    tickers = [p.ticker for p in context.positions]
    assert "AAPL" in tickers
    assert "BTC" in tickers

    aapl = next(p for p in context.positions if p.ticker == "AAPL")
    assert aapl.thesis_text is not None
    assert "AI growth" in aapl.thesis_text
    assert aapl.expected_return_pct == pytest.approx(0.20, abs=0.01)
    assert aapl.expected_hold_days == 180
    assert aapl.target_price == pytest.approx(180.0)
    assert aapl.stop_loss == pytest.approx(130.0)


@pytest.mark.asyncio
async def test_generate_summary_success():
    """Mock Claude API response, verify SummaryResult."""
    mock_response = _mock_anthropic_response("AAPL is tracking well.")

    agent = SummaryAgent(api_key="test-key-123")
    context = _make_context()

    with patch("agents.summary_agent.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        result = await agent.generate_summary(context)

    assert isinstance(result, SummaryResult)
    assert "AAPL is tracking well." in result.summary_text
    assert "This is not investment advice" in result.summary_text
    assert result.model == "claude-sonnet-4-20250514"
    assert result.input_tokens == 1500
    assert result.output_tokens == 400
    assert result.cost_usd > 0
    assert result.positions_covered == ["AAPL", "BTC"]


@pytest.mark.asyncio
async def test_generate_summary_no_api_key():
    """Raises clear error when no API key is provided."""
    agent = SummaryAgent(api_key=None)
    # Also clear env var
    with patch.dict("os.environ", {}, clear=True):
        agent_no_key = SummaryAgent(api_key=None)

    context = _make_context()
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        await agent_no_key.generate_summary(context)


@pytest.mark.asyncio
async def test_prompt_includes_thesis():
    """Verify thesis text appears in the prompt sent to Claude."""
    mock_response = _mock_anthropic_response("Summary with thesis.")

    agent = SummaryAgent(api_key="test-key")
    context = _make_context(with_thesis=True)

    with patch("agents.summary_agent.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        await agent.generate_summary(context)

        # Inspect the user message sent to Claude
        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        user_msg = messages[0]["content"]
        assert "Thesis:" in user_msg
        assert "AI growth" in user_msg
        assert "Expected Return:" in user_msg
        assert "Target Price:" in user_msg
        assert "Stop Loss:" in user_msg


@pytest.mark.asyncio
async def test_prompt_excludes_thesis_when_none():
    """Positions without thesis don't mention 'Thesis:' in prompt."""
    mock_response = _mock_anthropic_response("Summary without thesis.")

    agent = SummaryAgent(api_key="test-key")
    context = _make_context(with_thesis=False)

    with patch("agents.summary_agent.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        await agent.generate_summary(context)

        call_kwargs = mock_client.messages.create.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        user_msg = messages[0]["content"]
        # AAPL section should NOT contain "Thesis:" when thesis_text is None
        aapl_section = user_msg.split("### AAPL")[1].split("### BTC")[0]
        assert "Thesis:" not in aapl_section
        assert "Expected Return:" not in aapl_section


def test_cost_calculation():
    """Verify cost_usd computation from token counts."""
    cost = SummaryAgent._compute_cost(input_tokens=2000, output_tokens=500)
    # $3/M input * 2000 = $0.006; $15/M output * 500 = $0.0075
    expected = 0.006 + 0.0075
    assert cost == pytest.approx(expected, abs=1e-8)

    # Larger test
    cost2 = SummaryAgent._compute_cost(input_tokens=10_000, output_tokens=2_000)
    expected2 = 0.03 + 0.03
    assert cost2 == pytest.approx(expected2, abs=1e-8)


@pytest.mark.asyncio
async def test_summary_saved_to_db(db_path):
    """Verify DB write after generation."""
    result = SummaryResult(
        summary_text="Test summary.\n\n---\n*This is not investment advice.*",
        model="claude-sonnet-4-20250514",
        input_tokens=1500,
        output_tokens=400,
        cost_usd=0.0105,
        positions_covered=["AAPL", "BTC"],
    )
    row_id = await save_summary(db_path, result)
    assert row_id > 0

    # Verify we can read it back
    latest = await get_latest_summary(db_path)
    assert latest is not None
    assert latest["summary_text"] == result.summary_text
    assert latest["model"] == "claude-sonnet-4-20250514"
    assert latest["input_tokens"] == 1500
    assert latest["output_tokens"] == 400
    assert latest["cost_usd"] == pytest.approx(0.0105)
    assert latest["positions_covered"] == ["AAPL", "BTC"]


@pytest.mark.asyncio
async def test_api_endpoint_503_no_key(db_path):
    """POST /summary/generate returns 503 without API key."""
    from fastapi.testclient import TestClient
    from api.app import create_app

    app = create_app(db_path=db_path)

    with patch.dict("os.environ", {}, clear=False):
        # Ensure ANTHROPIC_API_KEY is not set
        import os
        env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with TestClient(app) as client:
                resp = client.post("/summary/generate")
                assert resp.status_code == 503
                body = resp.json()
                assert "error" in body
                assert body["error"]["code"] == "API_KEY_MISSING"
        finally:
            if env_backup is not None:
                os.environ["ANTHROPIC_API_KEY"] = env_backup
