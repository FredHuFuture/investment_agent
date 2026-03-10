from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Alert:
    """A single monitoring alert for a position."""

    ticker: str
    alert_type: str      # STOP_LOSS_HIT | TARGET_HIT | TIME_OVERRUN | SIGNIFICANT_LOSS | SIGNIFICANT_GAIN
    severity: str        # CRITICAL | HIGH | WARNING | INFO
    message: str
    recommended_action: str
    current_price: float | None = None
    trigger_price: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "recommended_action": self.recommended_action,
            "current_price": self.current_price,
            "trigger_price": self.trigger_price,
        }
