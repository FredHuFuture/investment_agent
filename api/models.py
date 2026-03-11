"""Pydantic v2 request/response models for the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------

class APIResponse(BaseModel):
    """Standard success envelope."""
    data: Any
    warnings: list[str] = []


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Any = None


class ErrorResponse(BaseModel):
    """Standard error envelope."""
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Portfolio requests
# ---------------------------------------------------------------------------

class AddPositionRequest(BaseModel):
    ticker: str
    asset_type: Literal["stock", "btc", "eth"] = "stock"
    quantity: float = Field(gt=0)
    avg_cost: float = Field(gt=0)
    entry_date: str  # YYYY-MM-DD
    sector: str | None = None
    industry: str | None = None


class SetCashRequest(BaseModel):
    amount: float = Field(ge=0)


class ScaleRequest(BaseModel):
    multiplier: float = Field(gt=0)


class SplitRequest(BaseModel):
    ticker: str
    ratio: int = Field(gt=0)


# ---------------------------------------------------------------------------
# Backtest requests
# ---------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    asset_type: Literal["stock", "btc", "eth"] = "stock"
    initial_capital: float = 100_000.0
    rebalance_frequency: Literal["daily", "weekly", "monthly"] = "weekly"
    agents: list[str] | None = None
    position_size_pct: float = 0.10
    stop_loss_pct: float | None = 0.10
    take_profit_pct: float | None = 0.20


class BatchBacktestRequest(BaseModel):
    tickers: list[str] = Field(min_length=1)
    agent_combos: list[list[str]] = Field(min_length=1)
    start_date: str
    end_date: str
    initial_capital: float = 100_000.0
    position_size_pct: float = 1.0
    rebalance_frequency: Literal["daily", "weekly", "monthly"] = "weekly"
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


# ---------------------------------------------------------------------------
# Daemon requests
# ---------------------------------------------------------------------------

class RunOnceRequest(BaseModel):
    job: Literal["daily", "weekly"]
