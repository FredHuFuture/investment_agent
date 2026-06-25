"""Execution adapter contract. Paper-only this milestone; never reaches a venue.

agents/ and engine/ MUST NOT import this package (see
tests/test_decision_import_boundary.py).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    ticker: str
    asset_type: str
    side: OrderSide
    quantity: float


@dataclass
class ExecutionReport:
    ticker: str
    side: str
    quantity: float
    fill_price: float
    status: str          # e.g. "FILLED"
    venue: str           # e.g. "PAPER"
    filled_at: str       # ISO-8601 UTC

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "side": self.side,
            "quantity": self.quantity,
            "fill_price": self.fill_price,
            "status": self.status,
            "venue": self.venue,
            "filled_at": self.filled_at,
        }


class ExecutionAdapter(ABC):
    """Abstract execution venue. Implementations fill an Order and report back."""

    @abstractmethod
    async def submit(self, order: Order) -> ExecutionReport:
        """Submit an order and return a fill report. Not assumed idempotent."""
        raise NotImplementedError
