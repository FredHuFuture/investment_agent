"""Paper execution adapter: fills at the current market price, no venue/network.

The price source is injectable for testing. By default it lazily uses the
existing data-provider factory (execution/ MAY import data_providers/).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable

from execution.adapter import ExecutionAdapter, ExecutionReport, Order

PriceFetchFn = Callable[[str, str], Awaitable[float]]


class PaperExecutionAdapter(ExecutionAdapter):
    """Simulated fills at the current price. ``venue`` is always ``"PAPER"``."""

    def __init__(self, price_fetch_fn: PriceFetchFn | None = None) -> None:
        self._price_fetch_fn = price_fetch_fn

    async def _fetch_price(self, ticker: str, asset_type: str) -> float:
        if self._price_fetch_fn is not None:
            return await self._price_fetch_fn(ticker, asset_type)
        # Lazy import keeps the dependency out of module import time.
        from data_providers.factory import get_provider

        provider = get_provider(asset_type)
        return float(await provider.get_current_price(ticker))

    async def submit(self, order: Order) -> ExecutionReport:
        price = await self._fetch_price(order.ticker, order.asset_type)
        return ExecutionReport(
            ticker=order.ticker,
            side=order.side.value,
            quantity=order.quantity,
            fill_price=float(price),
            status="FILLED",
            venue="PAPER",
            filled_at=datetime.now(timezone.utc).isoformat(),
        )
