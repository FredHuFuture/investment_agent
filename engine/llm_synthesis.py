"""UI-07: Opt-in Bull/Bear synthesis via Anthropic Claude.

Design constraints (from 04-RESEARCH.md):
1. MUST short-circuit when agent_input.backtest_mode=True — otherwise a
   3-year backtest would cost ~$2.78/ticker (Pitfall #5).
2. MUST NOT send dollar amounts, cost basis, or position sizes to the
   external API (Threat T-04-07 Information Disclosure / PII leak).
3. MUST NOT include thesis_text in the prompt (Threat T-04-06 prompt
   injection via user content).
4. MUST NOT raise — any failure degrades gracefully to None + warning.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from agents.models import AgentInput
from engine.aggregator import AggregatedSignal

try:
    from anthropic import AsyncAnthropic
except ImportError:  # pragma: no cover — optional dep
    AsyncAnthropic = None  # type: ignore[assignment,misc]

_logger = logging.getLogger("investment_agent.llm_synthesis")

_MODEL = "claude-sonnet-4-20250514"
_MAX_TOKENS = 500
_CACHE_TTL_SECONDS = 4 * 60 * 60  # 4 hours
_CACHE: dict[tuple, tuple[float, "LlmSynthesis"]] = {}

_SYSTEM_PROMPT = (
    "You are a financial analyst producing structured Bull/Bear synthesis "
    "for a portfolio monitoring system. You will be given aggregated agent "
    "signals for a single ticker. Return a JSON object with exactly three "
    "string fields: bull_case (1-2 sentences arguing for holding or buying), "
    "bear_case (1-2 sentences arguing against or for selling), and synthesis "
    "(1 sentence final recommendation). Do NOT speculate beyond the signal "
    "data provided. Do NOT mention dollar amounts or portfolio sizes. "
    "Return ONLY the JSON object, no markdown fences."
)


@dataclass
class LlmSynthesis:
    """Bull/Bear synthesis result from Anthropic Claude (UI-07)."""

    ticker: str
    bull_case: str
    bear_case: str
    synthesis: str
    model: str
    cached: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "bull_case": self.bull_case,
            "bear_case": self.bear_case,
            "synthesis": self.synthesis,
            "model": self.model,
            "cached": self.cached,
        }


def _is_enabled() -> bool:
    return os.getenv("ENABLE_LLM_SYNTHESIS", "false").lower() == "true"


def _build_prompt(aggregated: AggregatedSignal) -> str:
    """Build the user prompt with PII-safe signal metadata only.

    Intentionally omits: dollar amounts, cost basis, position sizes,
    thesis_text, user identifiers — per Threat T-04-06 and T-04-07.
    """
    agent_lines = []
    for out in aggregated.agent_signals:
        # Confidence bucketed to 10% increments — never raw dollar values
        bucket = int(round(out.confidence / 10.0) * 10)
        agent_lines.append(
            f"- {out.agent_name}: {out.signal.value} (confidence ~{bucket}%)"
        )
    regime_str = aggregated.regime.value if aggregated.regime else "NEUTRAL"
    confidence_bucket = int(round(aggregated.final_confidence / 10.0) * 10)
    return (
        f"Ticker: {aggregated.ticker}\n"
        f"Asset type: {aggregated.asset_type}\n"
        f"Overall signal: {aggregated.final_signal.value}\n"
        f"Confidence: ~{confidence_bucket}%\n"
        f"Regime: {regime_str}\n"
        f"Agent signals:\n" + "\n".join(agent_lines)
    )


def _cache_key(aggregated: AggregatedSignal) -> tuple:
    regime = aggregated.regime.value if aggregated.regime else "NEUTRAL"
    bucket = int(round(aggregated.final_confidence / 10.0) * 10)
    return (aggregated.ticker, aggregated.final_signal.value, regime, bucket)


def _cache_get(key: tuple) -> LlmSynthesis | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    ts, syn = entry
    if (time.time() - ts) > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    # Return as cached=True copy
    return LlmSynthesis(
        ticker=syn.ticker,
        bull_case=syn.bull_case,
        bear_case=syn.bear_case,
        synthesis=syn.synthesis,
        model=syn.model,
        cached=True,
    )


def _cache_put(key: tuple, synthesis: LlmSynthesis) -> None:
    _CACHE[key] = (time.time(), synthesis)


async def run_llm_synthesis(
    aggregated: AggregatedSignal,
    agent_input: AgentInput,
    client: Any | None = None,  # injectable for testing
) -> LlmSynthesis | None:
    """Optional post-aggregation Bull/Bear synthesis via Anthropic Claude.

    FOUND-04: MUST return None in backtest_mode to avoid API costs on
    historical loops (Pitfall #5 in 04-RESEARCH.md — ~$2.78/ticker on 3yr backtest).

    Order of checks (CRITICAL — do not reorder):
    1. backtest_mode short-circuit (FOUND-04) — FIRST, before everything
    2. ENABLE_LLM_SYNTHESIS flag check
    3. Anthropic SDK availability check
    4. ANTHROPIC_API_KEY presence check
    """
    # FOUND-04 short-circuit — DO NOT remove or reorder this check
    if agent_input.backtest_mode:
        _logger.debug(
            "LLM synthesis skipped for %s: backtest_mode=True (FOUND-04)",
            aggregated.ticker,
        )
        return None

    if not _is_enabled():
        return None

    if AsyncAnthropic is None:
        return None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    # Check cache (PII-safe key: ticker + signal + regime + confidence bucket)
    cache_key = _cache_key(aggregated)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Build prompt (NO dollar amounts, NO thesis_text per T-04-06/T-04-07)
    prompt = _build_prompt(aggregated)

    try:
        if client is None:
            client = AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
        parsed = json.loads(text)
        synthesis = LlmSynthesis(
            ticker=aggregated.ticker,
            bull_case=str(parsed.get("bull_case", "")),
            bear_case=str(parsed.get("bear_case", "")),
            synthesis=str(parsed.get("synthesis", "")),
            model=_MODEL,
            cached=False,
        )
        _cache_put(cache_key, synthesis)
        return synthesis
    except (json.JSONDecodeError, KeyError, AttributeError, IndexError) as exc:
        _logger.warning(
            "LLM synthesis JSON parse failed for %s: %s",
            aggregated.ticker,
            exc,
        )
        aggregated.warnings.append(f"LLM synthesis parse failed: {exc}")
        return None
    except Exception as exc:  # network, auth, rate-limit, etc.
        _logger.warning("LLM synthesis failed for %s: %s", aggregated.ticker, exc)
        aggregated.warnings.append(f"LLM synthesis failed: {exc}")
        return None
