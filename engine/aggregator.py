from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.models import AgentOutput, Regime, Signal

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
        }


class SignalAggregator:
    """Weighted aggregation of multiple agent signals.

    Phase 1: static default weights.
    Phase 2: learned weights from agent_performance table.
    """

    DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
        "stock": {
            "TechnicalAgent": 0.30,
            "FundamentalAgent": 0.45,
            "MacroAgent": 0.25,
        },
        "btc": {
            "CryptoAgent": 1.0,
        },
        "eth": {
            "CryptoAgent": 1.0,
        },
    }

    def __init__(
        self,
        weights: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self._weights = weights or self.DEFAULT_WEIGHTS

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

        weights = self._weights.get(asset_type, self._weights["stock"])
        warnings: list[str] = []

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
                "weighted_contribution": round(signal_value * agent_weight * confidence_factor, 4),
            }

        raw_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # --- Signal determination ---
        if raw_score >= 0.3:
            final_signal = Signal.BUY
        elif raw_score <= -0.3:
            final_signal = Signal.SELL
        else:
            final_signal = Signal.HOLD

        # --- Confidence calculation ---
        if final_signal == Signal.HOLD:
            confidence = 40.0 + (0.3 - abs(raw_score)) * (30.0 / 0.3)
        else:
            confidence = 50.0 + (abs(raw_score) - 0.3) * (40.0 / 0.7)
        confidence = max(30.0, min(90.0, confidence))

        # --- Consensus analysis ---
        signals = [o.signal for o in agent_outputs]
        buy_count = signals.count(Signal.BUY)
        sell_count = signals.count(Signal.SELL)
        hold_count = signals.count(Signal.HOLD)
        total = len(signals)
        max_count = max(buy_count, sell_count, hold_count)
        consensus_score = max_count / total if total > 0 else 0.0

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

        agree_count = max_count
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
