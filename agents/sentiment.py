"""SentimentAgent — analyses news headlines to produce a BUY/HOLD/SELL signal.

Analysis backends (in preference order):
1. **Anthropic Claude** — preferred when ``ANTHROPIC_API_KEY`` is set.
2. **FinBERT** (local) — used when Anthropic key is absent AND
   ``transformers`` + ``torch`` are installed (``pip install -e .[llm-local]``).
3. **HOLD fallback** — conservative HOLD @ 35 confidence when both paths are
   unavailable, with explicit warning.

Fully offline-safe: when the Anthropic SDK is missing or ``ANTHROPIC_API_KEY``
is not set and FinBERT is not installed, the agent returns a conservative HOLD
with a low-confidence warning instead of raising.

FinBERT import notes
--------------------
``transformers`` and ``torch`` are NOT imported at module load time — they are
~2 s cold-start even without downloading the model.  The import is deferred to
the first call of ``_try_load_finbert()``, which is only invoked inside
``analyze()`` when the Anthropic path is unavailable.

Pre-download helper::

    pip install -e .[llm-local]
    python scripts/fetch_finbert.py
"""
from __future__ import annotations

import asyncio
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

# ---------------------------------------------------------------------------
# Anthropic configuration
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# FinBERT lazy-import state
#
# These module-level flags track whether we have already attempted to import
# transformers.  We try at most once per process — if the import fails, we
# record that and skip subsequent attempts without re-raising ImportError.
#
# Tests that need to simulate different availability states should reset both
# flags via monkeypatch:
#   monkeypatch.setattr(agents.sentiment, "_FINBERT_IMPORT_ATTEMPTED", False)
#   monkeypatch.setattr(agents.sentiment, "_FINBERT_AVAILABLE", False)
# ---------------------------------------------------------------------------

_FINBERT_IMPORT_ATTEMPTED: bool = False
_FINBERT_AVAILABLE: bool = False


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# SentimentAgent
# ---------------------------------------------------------------------------

class SentimentAgent(BaseAgent):
    """Analyses news sentiment for a ticker.

    Backend preference: Anthropic Claude > FinBERT (local) > HOLD fallback.
    """

    def __init__(
        self,
        provider: DataProvider,
        news_provider: NewsProvider | None = None,
    ) -> None:
        super().__init__(provider)
        self._news_provider = news_provider
        # Lazy-loaded FinBERT pipeline; cached on the instance after first use.
        self._finbert_pipeline: Any = None

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
        * ``anthropic`` package not installed + FinBERT unavailable -> HOLD @ 35
        * ``ANTHROPIC_API_KEY`` unset + FinBERT unavailable          -> HOLD @ 35
        * ``ANTHROPIC_API_KEY`` unset + FinBERT available            -> FinBERT branch
        * No news provider configured                                 -> HOLD @ 40
        * No headlines found                                          -> HOLD @ 40
        * Anthropic API error                                         -> HOLD @ 35
        """
        self._validate_asset_type(agent_input)
        ticker = agent_input.ticker
        warnings: list[str] = []

        api_key = os.getenv("ANTHROPIC_API_KEY")
        use_anthropic = (AsyncAnthropic is not None) and bool(api_key)

        # Fetch headlines up-front — both Anthropic and FinBERT branches need them.
        headlines: list[NewsHeadline] = []
        if self._news_provider is not None:
            try:
                headlines = await self._news_provider.get_headlines(ticker, max_results=10)
            except Exception as exc:
                warnings.append(f"News fetch failed: {exc}")

        # Filter out stale headlines (>72h old) to avoid sentiment drift.
        headlines = _filter_recent(headlines, max_age_hours=72)

        if not headlines:
            return self._fallback_output(
                ticker,
                confidence=40.0,
                warning="No news headlines available for sentiment analysis.",
                extra_warnings=warnings,
            )

        # Branch 1: Anthropic (preferred when key is set and SDK available).
        if use_anthropic:
            return await self._analyze_with_anthropic(ticker, headlines, warnings, api_key)  # type: ignore[arg-type]

        # Branch 2: FinBERT local inference fallback.
        if self._try_load_finbert():
            try:
                out = await self._analyze_with_finbert(ticker, headlines)
                out.warnings = warnings + out.warnings
                return out
            except Exception as exc:
                warnings.append(f"FinBERT inference failed: {exc}")
                # Fall through to the HOLD branch below.

        # Branch 3: Both paths unavailable — conservative HOLD.
        if AsyncAnthropic is None:
            msg = (
                "Sentiment unavailable: anthropic package not installed "
                "and FinBERT not installed. "
                "Install one: pip install -e .[llm] OR pip install -e .[llm-local]"
            )
        else:
            msg = (
                "Sentiment unavailable: ANTHROPIC_API_KEY not set "
                "and FinBERT not installed. "
                "Set ANTHROPIC_API_KEY or run: pip install -e .[llm-local]"
            )
        return self._fallback_output(
            ticker,
            confidence=35.0,
            warning=msg,
            extra_warnings=warnings,
        )

    # ------------------------------------------------------------------
    # FinBERT helpers
    # ------------------------------------------------------------------

    def _try_load_finbert(self) -> bool:
        """Return True if FinBERT (transformers) is importable. Cached after first call.

        Does NOT actually load the pipeline — only checks import-ability.
        The actual pipeline load happens lazily in ``_get_finbert_pipeline()``.

        Notes:
            Uses module-level globals ``_FINBERT_IMPORT_ATTEMPTED`` and
            ``_FINBERT_AVAILABLE`` so that the import check happens at most
            once per process.  Tests can reset these via monkeypatch.
        """
        global _FINBERT_IMPORT_ATTEMPTED, _FINBERT_AVAILABLE  # noqa: PLW0603
        if _FINBERT_IMPORT_ATTEMPTED:
            return _FINBERT_AVAILABLE
        _FINBERT_IMPORT_ATTEMPTED = True
        try:
            from transformers import pipeline as _pipeline  # noqa: F401
            _FINBERT_AVAILABLE = True
        except ImportError:
            _FINBERT_AVAILABLE = False
            logger.info(
                "transformers not installed; FinBERT sentiment fallback disabled. "
                "Install with: pip install -e .[llm-local]"
            )
        return _FINBERT_AVAILABLE

    def _get_finbert_pipeline(self) -> Any:
        """Return the cached FinBERT pipeline, creating it on first call.

        Loads ``ProsusAI/finbert`` from HuggingFace hub on first invocation
        (may download ~400 MB if not cached).  Subsequent calls return the
        cached instance on ``self._finbert_pipeline``.
        """
        if self._finbert_pipeline is None:
            from transformers import pipeline  # type: ignore[import-not-found]
            logger.info(
                "Loading FinBERT pipeline (first call — may download ~400 MB if not cached)..."
            )
            self._finbert_pipeline = pipeline(
                "sentiment-analysis", model="ProsusAI/finbert"
            )
        return self._finbert_pipeline

    async def _analyze_with_finbert(
        self, ticker: str, headlines: list[NewsHeadline]
    ) -> AgentOutput:
        """Run local FinBERT inference over *headlines*.

        Requires ``>= 3`` headlines for a non-HOLD signal; fewer headlines
        yield an unreliable local inference and are treated as HOLD @ 40.

        FinBERT labels: ``"positive"`` | ``"negative"`` | ``"neutral"``

        Aggregation rule:
        - signed_score = +score for positive, -score for negative, 0 for neutral
        - mean_score = mean(signed_scores)
        - mean_score >= 0.25 -> BUY
        - mean_score <= -0.25 -> SELL
        - otherwise -> HOLD
        - confidence = min(90, max(30, 50 + abs(mean_score) * 100))
        """
        _MIN_HEADLINES = 3
        if len(headlines) < _MIN_HEADLINES:
            return self._fallback_output(
                ticker,
                confidence=40.0,
                warning=(
                    f"FinBERT requires >= {_MIN_HEADLINES} headlines for a "
                    f"non-HOLD signal; got {len(headlines)}."
                ),
            )

        pipe = self._get_finbert_pipeline()

        # Truncate at 512 chars — FinBERT tokeniser truncates at 512 tokens
        # and very long inputs slow CPU inference significantly.
        texts: list[str] = [
            (f"{h.title}. {h.snippet}" if h.snippet else h.title)[:512]
            for h in headlines
        ]

        # Run sync pipeline in a thread to avoid blocking the event loop.
        def _infer() -> list[dict[str, Any]]:
            return pipe(texts)  # type: ignore[return-value]

        results: list[dict[str, Any]] = await asyncio.to_thread(_infer)

        # Aggregate signed scores across all headlines.
        signed: list[float] = []
        for r in results:
            label = str(r.get("label", "neutral")).lower()
            score = float(r.get("score", 0.0))
            if label == "positive":
                signed.append(+score)
            elif label == "negative":
                signed.append(-score)
            # neutral contributes 0 — intentionally omitted from signed list
            # but still counted in len(results) for mean denominator

        if not results:
            return self._fallback_output(
                ticker,
                confidence=40.0,
                warning="FinBERT returned no results.",
            )

        # Mean over ALL results (neutral items contribute 0 to numerator)
        mean_score = sum(signed) / len(results)

        _BUY_THRESHOLD = 0.25
        _SELL_THRESHOLD = -0.25
        if mean_score >= _BUY_THRESHOLD:
            signal = Signal.BUY
            confidence = max(30.0, min(90.0, 50.0 + abs(mean_score) * 100.0))
        elif mean_score <= _SELL_THRESHOLD:
            signal = Signal.SELL
            confidence = max(30.0, min(90.0, 50.0 + abs(mean_score) * 100.0))
        else:
            signal = Signal.HOLD
            confidence = 40.0  # below threshold — low confidence HOLD

        return AgentOutput(
            agent_name=self.name,
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            reasoning=(
                f"FinBERT local inference on {len(headlines)} headlines; "
                f"mean sentiment score {mean_score:+.3f} -> {signal.value}. "
                f"Model: ProsusAI/finbert."
            ),
            metrics={
                "sentiment_score": mean_score,
                "catalyst_count": 0,        # FinBERT doesn't extract named catalysts
                "headline_count": len(headlines),
                "cost_usd": 0.0,            # local inference — no API cost
                "model": "ProsusAI/finbert",
                "inference": "local",
            },
            warnings=["Using FinBERT local inference (ANTHROPIC_API_KEY not set)."],
        )

    # ------------------------------------------------------------------
    # Anthropic helpers
    # ------------------------------------------------------------------

    async def _analyze_with_anthropic(
        self,
        ticker: str,
        headlines: list[NewsHeadline],
        warnings: list[str],
        api_key: str,
    ) -> AgentOutput:
        """Call the Claude API and return a sentiment AgentOutput."""
        user_message = _build_user_prompt(ticker, headlines)
        client = AsyncAnthropic(api_key=api_key)  # type: ignore[misc]

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
    # Shared helpers
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


# ---------------------------------------------------------------------------
# Standalone helpers
# ---------------------------------------------------------------------------

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
