from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from portfolio.models import Portfolio


class Signal(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class Regime(str, Enum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"


@dataclass
class AgentInput:
    ticker: str
    asset_type: str
    portfolio: Portfolio | None = None
    regime: Regime | None = None
    learned_weights: dict[str, Any] = field(default_factory=dict)
    approved_rules: list[str] = field(default_factory=list)


@dataclass
class AgentOutput:
    agent_name: str
    ticker: str
    signal: Signal
    confidence: float
    reasoning: str
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    warnings: list[str] = field(default_factory=list)
    data_completeness: float = 1.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not 0.0 <= self.confidence <= 100.0:
            raise ValueError(f"confidence must be 0-100, got {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "ticker": self.ticker,
            "signal": self.signal.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "warnings": self.warnings,
        }
