"""Tests for Plan 03-02: FinBERT local sentiment fallback in SentimentAgent.

All tests are fully offline — no actual FinBERT model download or Claude API
calls are made.  FinBERT availability is simulated by inserting / removing a
fake ``transformers`` module from ``sys.modules``.

Test catalogue (11 tests):
  T1  test_sentiment_prefers_anthropic_when_key_set
  T2  test_sentiment_uses_finbert_when_anthropic_key_unset
  T3  test_sentiment_uses_finbert_for_negative_headlines
  T4  test_sentiment_finbert_holds_on_mixed_low_score
  T5  test_sentiment_holds_when_finbert_unavailable
  T6  test_sentiment_holds_when_both_unavailable
  T7  test_sentiment_finbert_requires_3_headlines
  T8  test_sentiment_finbert_pipeline_cached_across_calls
  T9  test_sentiment_finbert_threshold_boundary
  T10 test_sentiment_regression_no_headlines_still_holds
  T11 test_sentiment_regression_anthropic_success_path_unchanged

Guard test (subprocess):
  test_import_does_not_pull_transformers — ensures ``import agents.sentiment``
  does NOT trigger ``import transformers`` or ``import torch``.
"""
from __future__ import annotations

import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import agents.sentiment as sentiment_module
from agents.models import AgentInput, AgentOutput, Signal
from agents.sentiment import SentimentAgent
from data_providers.news_provider import NewsHeadline, NewsProvider


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

class _StubDataProvider:
    """Minimal DataProvider stub — SentimentAgent only needs the constructor."""

    async def get_price_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> Any:
        return MagicMock()

    async def get_current_price(self, ticker: str) -> float:
        return 100.0

    async def get_key_stats(self, ticker: str) -> dict:
        return {}

    def is_point_in_time(self) -> bool:
        return False

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]


class _MockNewsProvider(NewsProvider):
    """In-memory news provider returning canned headlines."""

    def __init__(self, headlines: list[NewsHeadline] | None = None) -> None:
        self._headlines = headlines or []

    async def get_headlines(self, ticker: str, max_results: int = 10) -> list[NewsHeadline]:
        return self._headlines[:max_results]


def _make_agent_input(ticker: str = "AAPL", asset_type: str = "stock") -> AgentInput:
    return AgentInput(ticker=ticker, asset_type=asset_type)


def _recent_headlines(n: int, label: str = "positive", snippet: bool = False) -> list[NewsHeadline]:
    """Generate *n* headlines with timestamps within the 72-hour recency window."""
    now = datetime.now(timezone.utc)
    hl: list[NewsHeadline] = []
    for i in range(n):
        hl.append(
            NewsHeadline(
                title=f"Headline {i + 1}: {label} news for AAPL",
                source="TestSource",
                published_at=(now - timedelta(hours=i + 1)).isoformat(),
                snippet=f"Snippet {i + 1} with {label} tone." if snippet else None,
            )
        )
    return hl


# ---------------------------------------------------------------------------
# Fake FinBERT pipeline helpers
# ---------------------------------------------------------------------------

class _FakeFinbertPipe:
    """Synchronous fake of a transformers sentiment-analysis pipeline."""

    def __init__(
        self,
        label: str = "positive",
        score: float = 0.9,
        per_text: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Args:
            label: Default label for all texts.
            score: Default score for all texts.
            per_text: If provided, cycle through these results per text instead.
        """
        self._label = label
        self._score = score
        self._per_text = per_text

    def __call__(self, texts: list[str]) -> list[dict[str, Any]]:
        if self._per_text is not None:
            # Return per_text items cyclically, truncated to len(texts)
            results: list[dict[str, Any]] = []
            for i, _ in enumerate(texts):
                results.append(self._per_text[i % len(self._per_text)])
            return results
        return [{"label": self._label, "score": self._score} for _ in texts]


def _make_fake_transformers(pipe: Any) -> types.ModuleType:
    """Build a minimal fake ``transformers`` module with a ``pipeline`` factory."""
    call_count = 0

    def _pipeline_factory(*args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        return pipe

    def _get_call_count() -> int:
        return call_count

    mod = types.ModuleType("transformers")
    mod.pipeline = _pipeline_factory  # type: ignore[attr-defined]
    mod._get_call_count = _get_call_count  # type: ignore[attr-defined]
    return mod


def _reset_finbert_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset module-level FinBERT lazy-import state between tests."""
    monkeypatch.setattr(sentiment_module, "_FINBERT_IMPORT_ATTEMPTED", False)
    monkeypatch.setattr(sentiment_module, "_FINBERT_AVAILABLE", False)


# ---------------------------------------------------------------------------
# Guard test: module-level import must NOT pull transformers / torch
# ---------------------------------------------------------------------------

def test_import_does_not_pull_transformers() -> None:
    """Importing agents.sentiment must NOT cause transformers or torch to be imported."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from agents.sentiment import SentimentAgent; "
                "import sys; "
                "assert 'transformers' not in sys.modules, "
                "  f'transformers was pulled in at import time'; "
                "assert 'torch' not in sys.modules, "
                "  f'torch was pulled in at import time'; "
                "print('OK')"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Subprocess failed.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK" in result.stdout


# ---------------------------------------------------------------------------
# T1: Anthropic preferred when key is set
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_prefers_anthropic_when_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ANTHROPIC_API_KEY set, Anthropic path is used; FinBERT never loaded."""
    _reset_finbert_globals(monkeypatch)

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(5))
    agent = SentimentAgent(provider, news_provider=news)

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"signal":"BUY","confidence":80,"sentiment_score":0.7,"catalysts":["earnings"],"reasoning":"Strong beat."}')]
    mock_response.usage = MagicMock(input_tokens=500, output_tokens=100)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
        with patch("agents.sentiment.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.BUY
    # FinBERT pipeline must NOT have been loaded
    assert agent._finbert_pipeline is None


# ---------------------------------------------------------------------------
# T2: FinBERT used when Anthropic key is unset (positive headlines)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_uses_finbert_when_anthropic_key_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ANTHROPIC_API_KEY unset + transformers available, FinBERT returns BUY."""
    _reset_finbert_globals(monkeypatch)

    fake_pipe = _FakeFinbertPipe(label="positive", score=0.9)
    fake_transformers = _make_fake_transformers(fake_pipe)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(5))
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.BUY
    assert 50.0 <= result.confidence <= 90.0
    assert "FinBERT" in result.reasoning
    assert any("FinBERT" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# T3: FinBERT used when Anthropic key is unset (negative headlines -> SELL)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_uses_finbert_for_negative_headlines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ANTHROPIC_API_KEY unset + transformers available, bearish headlines -> SELL."""
    _reset_finbert_globals(monkeypatch)

    fake_pipe = _FakeFinbertPipe(label="negative", score=0.9)
    fake_transformers = _make_fake_transformers(fake_pipe)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(5, label="negative"))
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.SELL
    assert 50.0 <= result.confidence <= 90.0


# ---------------------------------------------------------------------------
# T4: FinBERT returns HOLD when mean score is below threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_finbert_holds_on_mixed_low_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mixed low-magnitude headlines -> mean_score near 0 -> HOLD @ 40."""
    _reset_finbert_globals(monkeypatch)

    # 2 positive (score 0.1), 2 negative (score 0.1), 1 neutral
    # mean = (2*0.1 - 2*0.1) / 5 = 0.0 -> HOLD
    per_text = [
        {"label": "positive", "score": 0.1},
        {"label": "negative", "score": 0.1},
        {"label": "positive", "score": 0.1},
        {"label": "negative", "score": 0.1},
        {"label": "neutral", "score": 0.6},
    ]
    fake_pipe = _FakeFinbertPipe(per_text=per_text)
    fake_transformers = _make_fake_transformers(fake_pipe)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(5))
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.HOLD
    assert result.confidence == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# T5: HOLD when FinBERT unavailable (transformers import fails)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_holds_when_finbert_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ANTHROPIC_API_KEY unset + transformers not importable -> HOLD @ 35."""
    _reset_finbert_globals(monkeypatch)

    # Simulate ImportError by inserting None into sys.modules["transformers"]
    monkeypatch.setitem(sys.modules, "transformers", None)  # type: ignore[arg-type]

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(5))
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.HOLD
    assert result.confidence == pytest.approx(35.0)
    assert any("FinBERT not installed" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# T6: HOLD when both Anthropic and FinBERT are unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_holds_when_both_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AsyncAnthropic=None AND transformers unavailable -> HOLD @ 35."""
    _reset_finbert_globals(monkeypatch)

    monkeypatch.setitem(sys.modules, "transformers", None)  # type: ignore[arg-type]

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(5))
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {}, clear=True):
        with patch("agents.sentiment.AsyncAnthropic", None):
            result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.HOLD
    assert result.confidence == pytest.approx(35.0)
    # Warning must mention the missing components
    combined = " ".join(result.warnings)
    assert "FinBERT not installed" in combined


# ---------------------------------------------------------------------------
# T7: FinBERT requires >= 3 headlines
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_finbert_requires_3_headlines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With only 2 headlines, FinBERT path returns HOLD @ 40."""
    _reset_finbert_globals(monkeypatch)

    fake_pipe = _FakeFinbertPipe(label="positive", score=0.95)
    fake_transformers = _make_fake_transformers(fake_pipe)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(2))  # only 2 headlines
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.HOLD
    assert result.confidence == pytest.approx(40.0)
    combined = " ".join(result.warnings)
    assert "3" in combined  # minimum mentioned in warning


# ---------------------------------------------------------------------------
# T8: FinBERT pipeline is cached across multiple analyze() calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_finbert_pipeline_cached_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running analyze() twice on the same agent creates the pipeline only once."""
    _reset_finbert_globals(monkeypatch)

    fake_pipe = _FakeFinbertPipe(label="positive", score=0.9)
    fake_transformers = _make_fake_transformers(fake_pipe)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(5))
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {}, clear=True):
        await agent.analyze(_make_agent_input())
        await agent.analyze(_make_agent_input())

    # The fake_transformers module tracks how many times pipeline() was called
    call_count: int = fake_transformers._get_call_count()  # type: ignore[attr-defined]
    assert call_count == 1, (
        f"Expected pipeline() to be called once, got {call_count}"
    )


# ---------------------------------------------------------------------------
# T9: FinBERT aggregation threshold boundary conditions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_finbert_threshold_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mean_score >= 0.25 -> BUY; mean_score < 0.25 -> HOLD."""
    # Scenario A: 5 headlines all positive at score 0.26/5 each won't work;
    # we need mean_score across all headlines.
    # With 5 positive headlines at score=0.26: mean = 0.26 -> BUY (>= 0.25)
    # With 5 positive headlines at score=0.24: mean = 0.24 -> HOLD (< 0.25)

    # --- Sub-scenario A: mean_score = 0.26 -> BUY ---
    _reset_finbert_globals(monkeypatch)

    fake_pipe_buy = _FakeFinbertPipe(label="positive", score=0.26)
    fake_transformers_buy = _make_fake_transformers(fake_pipe_buy)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers_buy)

    provider = _StubDataProvider()
    agent = SentimentAgent(provider, news_provider=_MockNewsProvider(_recent_headlines(5)))

    with patch.dict("os.environ", {}, clear=True):
        result_buy = await agent.analyze(_make_agent_input())

    assert result_buy.signal == Signal.BUY, (
        f"Expected BUY for mean_score=0.26, got {result_buy.signal}"
    )

    # --- Sub-scenario B: mean_score = 0.24 -> HOLD ---
    _reset_finbert_globals(monkeypatch)

    fake_pipe_hold = _FakeFinbertPipe(label="positive", score=0.24)
    fake_transformers_hold = _make_fake_transformers(fake_pipe_hold)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers_hold)

    agent2 = SentimentAgent(provider, news_provider=_MockNewsProvider(_recent_headlines(5)))

    with patch.dict("os.environ", {}, clear=True):
        result_hold = await agent2.analyze(_make_agent_input())

    assert result_hold.signal == Signal.HOLD, (
        f"Expected HOLD for mean_score=0.24, got {result_hold.signal}"
    )


# ---------------------------------------------------------------------------
# T10: Regression — no headlines still returns HOLD @ 40
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_regression_no_headlines_still_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty headlines list -> HOLD @ 40 (refactor must not break this path)."""
    _reset_finbert_globals(monkeypatch)

    provider = _StubDataProvider()
    news = _MockNewsProvider([])  # no headlines
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.HOLD
    assert result.confidence == pytest.approx(40.0)
    assert any("No news headlines" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# T11: Regression — Anthropic success path unchanged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_regression_anthropic_success_path_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic success path returns correct BUY signal and metrics (unchanged)."""
    _reset_finbert_globals(monkeypatch)

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(3))
    agent = SentimentAgent(provider, news_provider=news)

    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        text='{"signal":"SELL","confidence":65,"sentiment_score":-0.55,"catalysts":["guidance cut"],"reasoning":"Weak guidance issued."}'
    )]
    mock_response.usage = MagicMock(input_tokens=600, output_tokens=120)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
        with patch("agents.sentiment.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.SELL
    assert result.confidence == pytest.approx(65.0)
    assert result.metrics["sentiment_score"] == pytest.approx(-0.55)
    assert result.metrics["catalyst_count"] == 1
    assert result.metrics["model"] == "claude-sonnet-4-20250514"
    assert result.metrics["cost_usd"] > 0


# ---------------------------------------------------------------------------
# Bonus: Aggregation math verification (from plan spec)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sentiment_finbert_aggregation_math(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3 positive (0.9), 1 negative (0.6), 1 neutral -> mean ≈ 0.42 -> BUY @ 90."""
    _reset_finbert_globals(monkeypatch)

    # mean = (0.9 + 0.9 + 0.9 - 0.6 + 0) / 5 = 2.1 / 5 = 0.42
    per_text = [
        {"label": "positive", "score": 0.9},
        {"label": "positive", "score": 0.9},
        {"label": "positive", "score": 0.9},
        {"label": "negative", "score": 0.6},
        {"label": "neutral",  "score": 0.8},
    ]
    fake_pipe = _FakeFinbertPipe(per_text=per_text)
    fake_transformers = _make_fake_transformers(fake_pipe)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    provider = _StubDataProvider()
    news = _MockNewsProvider(_recent_headlines(5))
    agent = SentimentAgent(provider, news_provider=news)

    with patch.dict("os.environ", {}, clear=True):
        result = await agent.analyze(_make_agent_input())

    assert result.signal == Signal.BUY
    # confidence = min(90, 50 + 0.42*100) = min(90, 92) = 90
    assert result.confidence == pytest.approx(90.0)
    assert result.metrics["sentiment_score"] == pytest.approx(0.42, abs=0.01)
