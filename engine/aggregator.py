from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from agents.models import AgentOutput, Regime, Signal

if TYPE_CHECKING:
    from engine.llm_synthesis import LlmSynthesis

SIGNAL_VALUE: dict[Signal, float] = {
    Signal.BUY: +1.0,
    Signal.HOLD: 0.0,
    Signal.SELL: -1.0,
}


@dataclass
class AggregatedSignal:
    """Final combined signal from all agents."""

    ticker: str
    asset_type: str
    final_signal: Signal
    final_confidence: float          # 0-100
    regime: Regime | None            # from MacroAgent
    agent_signals: list[AgentOutput] # raw agent outputs
    reasoning: str                   # combined reasoning
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    ticker_info: dict[str, Any] = field(default_factory=dict)
    portfolio_impact: dict[str, Any] = field(default_factory=dict)
    # UI-07: optional Bull/Bear synthesis (None when ENABLE_LLM_SYNTHESIS=false or backtest_mode=True)
    llm_synthesis: "LlmSynthesis | None" = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "asset_type": self.asset_type,
            "final_signal": self.final_signal.value,
            "final_confidence": self.final_confidence,
            "regime": self.regime.value if self.regime else None,
            "agent_signals": [a.to_dict() for a in self.agent_signals],
            "reasoning": self.reasoning,
            "metrics": self.metrics,
            "warnings": self.warnings,
            "ticker_info": self.ticker_info,
            "portfolio_impact": self.portfolio_impact,
            "llm_synthesis": self.llm_synthesis.to_dict() if self.llm_synthesis is not None else None,
        }


class SignalAggregator:
    """Weighted aggregation of multiple agent signals.

    Phase 1: static default weights.
    Phase 2: learned weights from agent_performance table.
    """

    DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
        "stock": {
            "TechnicalAgent": 0.25,
            "FundamentalAgent": 0.40,
            "MacroAgent": 0.20,
            "SentimentAgent": 0.15,
        },
        "btc": {
            "CryptoAgent": 0.80,
            "TechnicalAgent": 0.20,
        },
        "eth": {
            "CryptoAgent": 0.80,
            "TechnicalAgent": 0.20,
        },
    }

    def __init__(
        self,
        weights: dict[str, dict[str, float]] | None = None,
        buy_threshold: float = 0.30,
        sell_threshold: float = -0.30,
    ) -> None:
        self._weights = weights or self.DEFAULT_WEIGHTS
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    def aggregate(
        self,
        agent_outputs: list[AgentOutput],
        ticker: str,
        asset_type: str,
    ) -> AggregatedSignal:
        """Aggregate all agent signals into a single final signal."""
        if not agent_outputs:
            return AggregatedSignal(
                ticker=ticker,
                asset_type=asset_type,
                final_signal=Signal.HOLD,
                final_confidence=30.0,
                regime=None,
                agent_signals=[],
                reasoning="No agent produced a signal.",
                metrics={
                    "raw_score": 0.0,
                    "consensus_score": 0.0,
                    "buy_count": 0,
                    "sell_count": 0,
                    "hold_count": 0,
                    "regime": None,
                    "weights_used": {},
                    "agent_contributions": {},
                },
                warnings=["No agent produced a signal."],
            )

        raw_weights = self._weights.get(asset_type, self._weights["stock"])
        warnings: list[str] = []

        # --- Weight renormalization (FOUND-05) ---
        # When fewer agents than expected are present (e.g., SentimentAgent offline),
        # scale remaining weights so they sum to exactly 1.0. Each weight is also
        # scaled by the agent's data_completeness before renormalization so agents
        # with partial data contribute proportionally less. Invariant validated by
        # tests/test_foundation_05_agent_renorm.py (parametrized across every
        # single-agent-disabled scenario for stock/btc/eth).
        present = {o.agent_name for o in agent_outputs}
        completeness_map = {
            o.agent_name: getattr(o, "data_completeness", 1.0)
            for o in agent_outputs
        }
        used_raw = {
            k: v * completeness_map.get(k, 1.0)
            for k, v in raw_weights.items()
            if k in present and v > 0
        }
        total_raw = sum(used_raw.values())
        weights = {k: v / total_raw for k, v in used_raw.items()} if total_raw > 0 else raw_weights

        # --- Weighted sum computation ---
        total_weight = 0.0
        weighted_sum = 0.0
        agent_contributions: dict[str, dict[str, Any]] = {}

        for output in agent_outputs:
            agent_weight = weights.get(output.agent_name, 0.0)
            if agent_weight == 0.0:
                continue
            signal_value = SIGNAL_VALUE[output.signal]
            confidence_factor = output.confidence / 100.0
            effective_weight = agent_weight * confidence_factor
            weighted_sum += signal_value * effective_weight
            total_weight += effective_weight
            agent_contributions[output.agent_name] = {
                "signal": output.signal.value,
                "confidence": output.confidence,
                "data_completeness": completeness_map.get(output.agent_name, 1.0),
                "weighted_contribution": round(signal_value * agent_weight * confidence_factor, 4),
            }

        # Use unnormalized weighted_sum so that agent confidence affects the
        # score and buy/sell thresholds remain meaningful.  With the old
        # normalization (weighted_sum / total_weight), a single agent always
        # produced raw_score = ±1.0, making thresholds irrelevant.
        raw_score = weighted_sum

        # --- Signal determination ---
        bt = self._buy_threshold
        st = self._sell_threshold
        if raw_score >= bt:
            final_signal = Signal.BUY
        elif raw_score <= st:
            final_signal = Signal.SELL
        else:
            final_signal = Signal.HOLD

        # --- Confidence calculation ---
        if final_signal == Signal.HOLD:
            confidence = 40.0 + (bt - abs(raw_score)) * (30.0 / bt) if bt > 0 else 50.0
        else:
            confidence = 50.0 + (abs(raw_score) - bt) * (40.0 / (1.0 - bt)) if bt < 1.0 else 70.0
        confidence = max(30.0, min(90.0, confidence))

        # --- Consensus analysis (confidence-weighted) ---
        signals = [o.signal for o in agent_outputs]
        buy_count = signals.count(Signal.BUY)
        sell_count = signals.count(Signal.SELL)
        hold_count = signals.count(Signal.HOLD)
        # Weight each agent's vote by its confidence for more accurate consensus
        buy_conf = sum(o.confidence for o in agent_outputs if o.signal == Signal.BUY)
        sell_conf = sum(o.confidence for o in agent_outputs if o.signal == Signal.SELL)
        hold_conf = sum(o.confidence for o in agent_outputs if o.signal == Signal.HOLD)
        total_conf = buy_conf + sell_conf + hold_conf
        consensus_score = max(buy_conf, sell_conf, hold_conf) / total_conf if total_conf > 0 else 0.0

        if consensus_score < 0.5:
            confidence *= 0.8
            warnings.append("Low agent consensus -- signals conflict.")

        confidence = max(30.0, min(90.0, confidence))

        # --- Regime extraction ---
        regime: Regime | None = None
        macro_net_score: int | None = None
        for output in agent_outputs:
            if output.agent_name == "MacroAgent":
                regime_str = output.metrics.get("regime")
                if regime_str:
                    try:
                        regime = Regime(regime_str)
                    except ValueError:
                        pass
                macro_net_score = output.metrics.get("net_score")
                break

        # --- Reasoning string ---
        agent_parts = []
        for output in agent_outputs:
            short_name = output.agent_name.replace("Agent", "")
            agent_parts.append(f"{short_name}={output.signal.value}({output.confidence:.0f})")
        agents_str = ", ".join(agent_parts)

        total = len(signals)
        agree_count = max(buy_count, sell_count, hold_count)
        if consensus_score >= 1.0:
            consensus_str = f"{agree_count}/{total} agents agree (strong consensus)"
        elif consensus_score >= 0.5:
            consensus_str = f"{agree_count}/{total} agents agree"
        else:
            consensus_str = f"{agree_count}/{total} agents -- LOW CONSENSUS, reduced confidence"

        if regime is not None:
            regime_display = regime.value
            if macro_net_score is not None:
                score_sign = "+" if macro_net_score >= 0 else ""
                regime_display += f" (net score {score_sign}{macro_net_score})"
        else:
            regime_display = "NEUTRAL"

        weights_parts = [
            f"{name.replace('Agent', '')} {w}"
            for name, w in weights.items()
        ]
        weights_str = ", ".join(weights_parts)

        score_sign = "+" if raw_score >= 0 else ""
        reasoning = (
            f"Final: {final_signal.value} (score {score_sign}{raw_score:.2f}, confidence {confidence:.0f}).\n"
            f" Agents: {agents_str}.\n"
            f" Consensus: {consensus_str}.\n"
            f" Regime: {regime_display}.\n"
            f" Weights: {weights_str}."
        )

        metrics: dict[str, Any] = {
            "raw_score": round(raw_score, 4),
            "consensus_score": round(consensus_score, 4),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "hold_count": hold_count,
            "regime": regime.value if regime else None,
            "weights_used": weights,
            "agent_contributions": agent_contributions,
            "buy_threshold": self._buy_threshold,
            "sell_threshold": self._sell_threshold,
        }

        return AggregatedSignal(
            ticker=ticker,
            asset_type=asset_type,
            final_signal=final_signal,
            final_confidence=round(confidence, 2),
            regime=regime,
            agent_signals=agent_outputs,
            reasoning=reasoning,
            metrics=metrics,
            warnings=warnings,
        )

    def aggregate_with_regime(
        self,
        agent_outputs: list[AgentOutput],
        ticker: str,
        asset_type: str,
        regime_adjustments: dict[str, float] | None = None,
    ) -> AggregatedSignal:
        """Aggregate signals with optional regime-based weight adjustments.

        regime_adjustments: dict mapping agent_name -> multiplier
            (e.g., 1.2 = 20% more weight).
        After applying multipliers, weights are re-normalized to sum to 1.0.

        If regime_adjustments is None or empty, falls back to standard aggregate().
        """
        if not regime_adjustments:
            return self.aggregate(agent_outputs, ticker, asset_type)

        # Get base weights for this asset type
        raw_weights = self._weights.get(asset_type, self._weights.get("stock", {}))

        # Apply regime multipliers
        adjusted: dict[str, float] = {}
        for agent_name, base_weight in raw_weights.items():
            multiplier = regime_adjustments.get(agent_name, 1.0)
            adjusted[agent_name] = base_weight * multiplier

        # Re-normalize so weights sum to 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        # Build a temporary aggregator with the regime-adjusted weights and
        # delegate to the standard aggregate() method.
        regime_aggregator = SignalAggregator(
            weights={asset_type: adjusted},
            buy_threshold=self._buy_threshold,
            sell_threshold=self._sell_threshold,
        )
        result = regime_aggregator.aggregate(agent_outputs, ticker, asset_type)

        # Tag metrics so callers know regime adjustments were applied
        result.metrics["regime_adjustments"] = regime_adjustments
        result.metrics["regime_adjusted_weights"] = adjusted

        return result
