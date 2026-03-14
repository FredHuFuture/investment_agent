"""Tests for Sprint 10.1/10.3: SentimentAgent and Aggregator Integration.

All tests are fully offline — Claude API and news providers are mocked.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.models import AgentInput, AgentOutput, Signal
from agents.sentiment import SentimentAgent, parse_sentiment_response
from data_providers.news_provider import NewsHeadline, NewsProvider
from engine.aggregator import SignalAggregator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _StubDataProvider:
    """Minimal stand-in for DataProvider so SentimentAgent can be instantiated."""

    async def get_price_history(self, ticker, period="1y", interval="1d"):
        return MagicMock()

    async def get_current_price(self, ticker):
        return 100.0

    async def get_key_stats(self, ticker):
        return {}

    def is_point_in_time(self):
        return False

    def supported_asset_types(self):
        return ["stock", "btc", "eth"]


class _MockNewsProvider(NewsProvider):
    """In-memory news provider returning canned headlines."""

    def __init__(self, headlines: list[NewsHeadline] | None = None) -> None:
        self._headlines = headlines or []

    async def get_headlines(self, ticker: str, max_results: int = 10) -> list[NewsHeadline]:
        return self._headlines[:max_results]


def _sample_headlines() -> list[NewsHeadline]:
    """Return a small set of test headlines."""
    return [
        NewsHeadline(
            title="AAPL beats Q1 earnings expectations",
            source="Reuters",
            published_at="2026-03-10T14:00:00Z",
            url="https://example.com/1",
            snippet="Apple reported strong results driven by Services growth.",
        ),
        NewsHeadline(
            title="AAPL announces record buyback programme",
            source="Bloomberg",
            published_at="2026-03-09T10:00:00Z",
            url="https://example.com/2",
        ),
        NewsHeadline(
            title="Concerns about iPhone sales in China",
            source="CNBC",
            published_at="2026-03-08T08:00:00Z",
        ),
    ]


def _make_agent_input(ticker: str = "AAPL", asset_type: str = "stock") -> AgentInput:
    return AgentInput(ticker=ticker, asset_type=asset_type)


def _mock_claude_response(
    signal: str = "BUY",
    confidence: int = 72,
    sentiment_score: float = 0.65,
    catalysts: list[str] | None = None,
    reasoning: str = "Strong earnings and buyback signal positive momentum.",
) -> MagicMock:
    """Build a mock Anthropic Messages response returning valid JSON."""
    payload = {
        "signal": signal,
        "confidence": confidence,
        "sentiment_score": sentiment_score,
        "catalysts": catalysts or ["earnings beat", "buyback programme"],
        "reasoning": reasoning,
    }
    content_block = MagicMock()
    content_block.text = json.dumps(payload)

    usage = MagicMock()
    usage.input_tokens = 800
    usage.output_tokens = 150

    response = MagicMock()
    response.content = [content_block]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_agent_no_api_key():
    """Without ANTHROPIC_API_KEY env var, returns HOLD with a warning."""
    provider = _StubDataProvider()
    news = _MockNewsProvider(_sample_headlines())
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.HOLD
    assert result.confidence == 35.0
    assert any("ANTHROPIC_API_KEY" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_sentiment_agent_no_news_provider():
    """Without a news provider, returns HOLD with low confidence."""
    provider = _StubDataProvider()
    agent = SentimentAgent(provider, news_provider=None)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.HOLD
    assert result.confidence == 40.0
    assert any("No news headlines" in w for w in result.warnings)


def test_sentiment_agent_name_and_types():
    """Verify name='SentimentAgent' and supported asset types."""
    provider = _StubDataProvider()
    agent = SentimentAgent(provider)

    assert agent.name == "SentimentAgent"
    assert "stock" in agent.supported_asset_types()
    assert "btc" in agent.supported_asset_types()
    assert "eth" in agent.supported_asset_types()


def test_sentiment_parse_response():
    """Test JSON parsing logic with a well-formed Claude response."""
    raw_json = json.dumps({
        "signal": "BUY",
        "confidence": 78,
        "sentiment_score": 0.72,
        "catalysts": ["earnings beat", "guidance raise"],
        "reasoning": "Positive earnings surprise.",
    })
    parsed = parse_sentiment_response(raw_json)

    assert parsed["signal"] == "BUY"
    assert parsed["confidence"] == 78
    assert parsed["sentiment_score"] == pytest.approx(0.72)
    assert len(parsed["catalysts"]) == 2
    assert "Positive earnings surprise." in parsed["reasoning"]


def test_sentiment_parse_response_with_markdown_fences():
    """Parsing handles markdown code fences around JSON."""
    raw = '```json\n{"signal":"SELL","confidence":60,"sentiment_score":-0.5,"catalysts":[],"reasoning":"Bearish."}\n```'
    parsed = parse_sentiment_response(raw)
    assert parsed["signal"] == "SELL"
    assert parsed["confidence"] == 60
    assert parsed["sentiment_score"] == pytest.approx(-0.5)


def test_sentiment_parse_response_invalid_json():
    """Malformed input falls back to HOLD."""
    parsed = parse_sentiment_response("this is not json at all")
    assert parsed["signal"] == "HOLD"
    assert parsed["confidence"] == 35


def test_aggregator_weights_include_sentiment():
    """DEFAULT_WEIGHTS['stock'] includes SentimentAgent at 0.15."""
    weights = SignalAggregator.DEFAULT_WEIGHTS["stock"]
    assert "SentimentAgent" in weights
    assert weights["SentimentAgent"] == pytest.approx(0.15)
    # Sum should be 1.0
    assert sum(weights.values()) == pytest.approx(1.0)


def test_aggregator_renormalizes_without_sentiment():
    """When SentimentAgent output is missing, other weights renormalize to 1.0."""
    aggregator = SignalAggregator()

    # Create outputs from only the three non-sentiment agents
    outputs = [
        AgentOutput(
            agent_name="TechnicalAgent",
            ticker="AAPL",
            signal=Signal.BUY,
            confidence=70.0,
            reasoning="bullish cross",
        ),
        AgentOutput(
            agent_name="FundamentalAgent",
            ticker="AAPL",
            signal=Signal.BUY,
            confidence=65.0,
            reasoning="strong fundamentals",
        ),
        AgentOutput(
            agent_name="MacroAgent",
            ticker="AAPL",
            signal=Signal.HOLD,
            confidence=50.0,
            reasoning="neutral macro",
        ),
    ]

    result = aggregator.aggregate(outputs, "AAPL", "stock")

    # Verify the used weights were renormalized (SentimentAgent excluded)
    used_weights = result.metrics["weights_used"]
    assert "SentimentAgent" not in used_weights
    assert sum(used_weights.values()) == pytest.approx(1.0)
    # The original ratios (0.25 : 0.40 : 0.20) should be preserved
    assert used_weights["TechnicalAgent"] == pytest.approx(0.25 / 0.85, abs=0.001)
    assert used_weights["FundamentalAgent"] == pytest.approx(0.40 / 0.85, abs=0.001)
    assert used_weights["MacroAgent"] == pytest.approx(0.20 / 0.85, abs=0.001)


@pytest.mark.asyncio
async def test_sentiment_metrics_structure():
    """Verify metrics dict has all expected keys after a successful call."""
    provider = _StubDataProvider()
    news = _MockNewsProvider(_sample_headlines())
    agent = SentimentAgent(provider, news_provider=news)

    mock_response = _mock_claude_response()

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
        with patch("agents.sentiment.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.BUY
    assert result.confidence == 72.0

    expected_keys = {"sentiment_score", "catalyst_count", "headline_count", "cost_usd", "model"}
    assert expected_keys.issubset(set(result.metrics.keys()))

    assert result.metrics["sentiment_score"] == pytest.approx(0.65)
    assert result.metrics["catalyst_count"] == 2
    assert result.metrics["headline_count"] == 3
    assert result.metrics["cost_usd"] > 0
    assert result.metrics["model"] == "claude-sonnet-4-20250514"


@pytest.mark.asyncio
async def test_sentiment_agent_empty_headlines():
    """News provider returns empty list -> HOLD with confidence 40."""
    provider = _StubDataProvider()
    news = _MockNewsProvider([])  # no headlines
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.HOLD
    assert result.confidence == 40.0
    assert any("No news headlines" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_sentiment_agent_no_anthropic_module():
    """When anthropic package is not installed, returns HOLD with warning."""
    provider = _StubDataProvider()
    news = _MockNewsProvider(_sample_headlines())
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
        with patch("agents.sentiment.AsyncAnthropic", None):
            result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.HOLD
    assert result.confidence == 35.0
    assert any("anthropic package not installed" in w for w in result.warnings)
