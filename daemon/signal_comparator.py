"""Pure signal comparison logic -- no I/O."""
from __future__ import annotations

from dataclasses import dataclass

_DIRECTIONAL = {"BUY", "SELL"}


@dataclass
class SignalComparison:
    """Result of comparing thesis signal to current re-analysis signal."""

    original_signal: str        # "BUY" | "HOLD" | "SELL"
    current_signal: str         # "BUY" | "HOLD" | "SELL"
    original_confidence: float
    current_confidence: float
    direction_reversed: bool    # True only for BUY->SELL or SELL->BUY
    confidence_delta: float     # current_confidence - original_confidence

    @property
    def summary(self) -> str:
        if self.direction_reversed:
            return (
                f"REVERSAL: {self.original_signal} -> {self.current_signal} "
                f"(confidence: {self.original_confidence:.0f} -> {self.current_confidence:.0f})"
            )
        return (
            f"No change: {self.original_signal} -> {self.current_signal} "
            f"(confidence delta: {self.confidence_delta:+.0f})"
        )


def compare_signals(
    original_signal: str,
    original_confidence: float,
    current_signal: str,
    current_confidence: float,
) -> SignalComparison:
    """Compare original thesis signal to current re-analysis signal.

    A direction reversal is:
    - BUY -> SELL
    - SELL -> BUY

    BUY -> HOLD or SELL -> HOLD is a weakening, NOT a full reversal.
    HOLD -> BUY/SELL is a new directional signal, NOT a reversal.

    Args:
        original_signal: Signal string from positions_thesis.expected_signal
        original_confidence: From positions_thesis.expected_confidence
        current_signal: Signal string from new AggregatedSignal.final_signal.value
        current_confidence: From new AggregatedSignal.final_confidence

    Returns:
        SignalComparison with direction_reversed flag and metadata.
    """
    direction_reversed = (
        original_signal in _DIRECTIONAL
        and current_signal in _DIRECTIONAL
        and original_signal != current_signal
    )

    return SignalComparison(
        original_signal=original_signal,
        current_signal=current_signal,
        original_confidence=original_confidence,
        current_confidence=current_confidence,
        direction_reversed=direction_reversed,
        confidence_delta=current_confidence - original_confidence,
    )
