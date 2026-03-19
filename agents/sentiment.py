"""SentimentAgent — analyses news headlines via Claude API to produce a
BUY/HOLD/SELL signal based on overall sentiment.

Fully offline-safe: when the Anthropic SDK is missing or ``ANTHROPIC_API_KEY``
is not set, the agent returns a conservative HOLD with a low-confidence
warning instead of raising.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from agents.base import BaseAgent
from agents.models import AgentInput, AgentOutput, Signal
from data_providers.base import DataProvider
from data_providers.news_provider import NewsHeadline, NewsProvider

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Claude Sonnet pricing (USD per token)
_INPUT_PRICE_PER_TOKEN = 3.0 / 1_000_000   # $3 / 1M input tokens
_OUTPUT_PRICE_PER_TOKEN = 15.0 / 1_000_000  # $15 / 1M output tokens

_MODEL = "claude-sonnet-4-20250514"

_SYSTEM_PROMPT = """\
You are a financial news sentiment analysis engine.  Your job is to read a
set of recent news headlines (and optional snippets) for a given ticker symbol
and produce a structured sentiment assessment.

Rules:
1. Analyse ONLY the sentiment conveyed by the headlines — do NOT speculate
   beyond what the text says.
2. Do NOT give investment advice.  You are objectively measuring sentiment,
   not recommending trades.
3. Return your answer as a single valid JSON object with these fields:
   - "signal": one of "BUY", "HOLD", or "SELL"
   - "confidence": integer 0-100
   - "sentiment_score": float from -1.0 (extremely negative) to +1.0 (extremely positive)
   - "catalysts": list of short strings describing key catalysts you identified
   - "reasoning": a brief (1-3 sentence) explanation of your assessment

Return ONLY the JSON object, no markdown fences, no commentary.
"""


def _build_user_prompt(ticker: str, headlines: list[NewsHeadline]) -> str:
    """Build the user message listing headlines for Claude to analyse."""
    lines: list[str] = [
        f"Ticker: {ticker}",
        f"Number of headlines: {len(headlines)}",
        "",
        "Headlines:",
    ]
    for i, h in enumerate(headlines, 1):
        entry = f"{i}. [{h.source}] {h.title} (published {h.published_at})"
        if h.snippet:
            entry += f"\n   Snippet: {h.snippet}"
        lines.append(entry)
    lines.append("")
    lines.append(
        "Analyse the sentiment of these headlines and return your JSON assessment."
    )
    return "\n".join(lines)


def parse_sentiment_response(text: str) -> dict[str, Any]:
    """Parse the JSON response from Claude, with fallback handling.

    Returns a dict with keys: signal, confidence, sentiment_score, catalysts,
    reasoning.  Falls back to HOLD if parsing fails.
    """
    # Strip markdown fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (possibly ```json)
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "signal": "HOLD",
            "confidence": 35,
            "sentiment_score": 0.0,
            "catalysts": [],
            "reasoning": "Failed to parse Claude response as JSON.",
        }

    # Normalise / validate fields
    raw_signal = str(data.get("signal", "HOLD")).upper()
    if raw_signal not in ("BUY", "HOLD", "SELL"):
        raw_signal = "HOLD"

    confidence = data.get("confidence", 50)
    try:
        confidence = int(confidence)
    except (TypeError, ValueError):
        confidence = 50
    confidence = max(0, min(100, confidence))

    sentiment_score = data.get("sentiment_score", 0.0)
    try:
        sentiment_score = float(sentiment_score)
    except (TypeError, ValueError):
        sentiment_score = 0.0
    sentiment_score = max(-1.0, min(1.0, sentiment_score))

    catalysts = data.get("catalysts", [])
    if not isinstance(catalysts, list):
        catalysts = []

    reasoning = str(data.get("reasoning", ""))

    return {
        "signal": raw_signal,
        "confidence": confidence,
        "sentiment_score": sentiment_score,
        "catalysts": catalysts,
        "reasoning": reasoning,
    }


class SentimentAgent(BaseAgent):
    """Analyses news sentiment for a ticker using the Claude API."""

    def __init__(
        self,
        provider: DataProvider,
        news_provider: NewsProvider | None = None,
    ) -> None:
        super().__init__(provider)
        self._news_provider = news_provider

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:  # type: ignore[override]
        return "SentimentAgent"

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        """Run sentiment analysis on recent headlines for *agent_input.ticker*.

        Gracefully degrades when:
        * ``anthropic`` package is not installed  -> HOLD @ 35
        * ``ANTHROPIC_API_KEY`` env var is missing -> HOLD @ 35
        * No news provider is configured          -> HOLD @ 40
        * No headlines are found                   -> HOLD @ 40
        """
        self._validate_asset_type(agent_input)
        ticker = agent_input.ticker
        warnings: list[str] = []

        # 1. Check that the Anthropic SDK is available
        if AsyncAnthropic is None:
            return self._fallback_output(
                ticker,
                confidence=35.0,
                warning="anthropic package not installed — sentiment analysis unavailable.",
            )

        # 2. Check for API key
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return self._fallback_output(
                ticker,
                confidence=35.0,
                warning="ANTHROPIC_API_KEY not set — sentiment analysis unavailable.",
            )

        # 3. Fetch headlines
        headlines: list[NewsHeadline] = []
        if self._news_provider is not None:
            try:
                headlines = await self._news_provider.get_headlines(ticker, max_results=10)
            except Exception as exc:
                warnings.append(f"News fetch failed: {exc}")

        # Filter out stale headlines (>72h old) to avoid sentiment drift
        headlines = _filter_recent(headlines, max_age_hours=72)

        if not headlines:
            return self._fallback_output(
                ticker,
                confidence=40.0,
                warning="No news headlines available for sentiment analysis.",
                extra_warnings=warnings,
            )

        # 4. Call Claude API
        user_message = _build_user_prompt(ticker, headlines)
        client = AsyncAnthropic(api_key=api_key)

        try:
            response = await client.messages.create(
                model=_MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as exc:
            warnings.append(f"Claude API call failed: {exc}")
            return self._fallback_output(
                ticker,
                confidence=35.0,
                warning=f"Claude API call failed: {exc}",
                extra_warnings=warnings,
            )

        # 5. Parse response
        raw_text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = (
            input_tokens * _INPUT_PRICE_PER_TOKEN
            + output_tokens * _OUTPUT_PRICE_PER_TOKEN
        )

        parsed = parse_sentiment_response(raw_text)

        signal = Signal(parsed["signal"])
        confidence = self._clamp_confidence(float(parsed["confidence"]))

        return AgentOutput(
            agent_name=self.name,
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            reasoning=parsed["reasoning"],
            metrics={
                "sentiment_score": parsed["sentiment_score"],
                "catalyst_count": len(parsed["catalysts"]),
                "headline_count": len(headlines),
                "cost_usd": round(cost_usd, 6),
                "model": _MODEL,
            },
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fallback_output(
        self,
        ticker: str,
        *,
        confidence: float,
        warning: str,
        extra_warnings: list[str] | None = None,
    ) -> AgentOutput:
        """Return a conservative HOLD output when sentiment cannot be computed."""
        all_warnings = list(extra_warnings) if extra_warnings else []
        all_warnings.append(warning)
        return AgentOutput(
            agent_name=self.name,
            ticker=ticker,
            signal=Signal.HOLD,
            confidence=confidence,
            reasoning=warning,
            metrics={
                "sentiment_score": 0.0,
                "catalyst_count": 0,
                "headline_count": 0,
                "cost_usd": 0.0,
                "model": _MODEL,
            },
            warnings=all_warnings,
        )


def _filter_recent(
    headlines: list[NewsHeadline],
    max_age_hours: int = 72,
) -> list[NewsHeadline]:
    """Drop headlines older than *max_age_hours* to avoid stale sentiment."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    recent: list[NewsHeadline] = []
    for h in headlines:
        try:
            pub = datetime.fromisoformat(h.published_at.replace("Z", "+00:00"))
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if pub >= cutoff:
                recent.append(h)
        except (ValueError, TypeError, AttributeError):
            # If we can't parse the date, keep the headline (safe fallback)
            recent.append(h)
    return recent
