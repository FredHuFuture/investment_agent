from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class Position:
    ticker: str
    asset_type: str
    quantity: float
    avg_cost: float
    current_price: float = 0.0
    sector: str | None = None
    industry: str | None = None
    entry_date: str = ""
    original_analysis_id: int | None = None
    expected_return_pct: float | None = None
    expected_hold_days: int | None = None
    thesis_text: str | None = None
    target_price: float | None = None
    stop_loss: float | None = None

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis

    @property
    def holding_days(self) -> int:
        """Days from entry_date to today."""
        if not self.entry_date:
            return 0
        try:
            entry = date.fromisoformat(self.entry_date)
        except ValueError:
            return 0
        delta = date.today() - entry
        return max(delta.days, 0)

    @classmethod
    def from_db_row(cls, row: tuple) -> "Position":
        pos = cls(
            ticker=row[0],
            asset_type=row[1],
            quantity=float(row[2]),
            avg_cost=float(row[3]),
            sector=row[4],
            industry=row[5],
            entry_date=row[6],
            original_analysis_id=row[7],
            expected_return_pct=row[8],
            expected_hold_days=row[9],
        )
        # Extended columns from LEFT JOIN with positions_thesis
        if len(row) > 10:
            pos.thesis_text = row[10]
            pos.target_price = float(row[11]) if row[11] is not None else None
            pos.stop_loss = float(row[12]) if row[12] is not None else None
        return pos

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "asset_type": self.asset_type,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "current_price": self.current_price,
            "sector": self.sector,
            "industry": self.industry,
            "entry_date": self.entry_date,
            "original_analysis_id": self.original_analysis_id,
            "expected_return_pct": self.expected_return_pct,
            "expected_hold_days": self.expected_hold_days,
            "thesis_text": self.thesis_text,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "market_value": self.market_value,
            "cost_basis": self.cost_basis,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "holding_days": self.holding_days,
        }


@dataclass
class Portfolio:
    positions: list[Position]
    cash: float
    total_value: float
    stock_exposure_pct: float
    crypto_exposure_pct: float
    cash_pct: float
    sector_breakdown: dict[str, float]
    top_concentration: list[tuple[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "positions": [position.to_dict() for position in self.positions],
            "cash": self.cash,
            "total_value": self.total_value,
            "stock_exposure_pct": self.stock_exposure_pct,
            "crypto_exposure_pct": self.crypto_exposure_pct,
            "cash_pct": self.cash_pct,
            "sector_breakdown": self.sector_breakdown,
            "top_concentration": self.top_concentration,
        }
