from __future__ import annotations

from execution.adapter import Order, OrderSide
from execution.paper import PaperExecutionAdapter


async def test_paper_fill_uses_injected_price() -> None:
    async def fake_price(ticker: str, asset_type: str) -> float:
        assert ticker == "AAPL" and asset_type == "stock"
        return 200.0

    adapter = PaperExecutionAdapter(price_fetch_fn=fake_price)
    order = Order(ticker="AAPL", asset_type="stock", side=OrderSide.BUY, quantity=2.0)
    report = await adapter.submit(order)

    assert report.status == "FILLED"
    assert report.venue == "PAPER"
    assert report.fill_price == 200.0
    assert report.quantity == 2.0
    assert report.side == "BUY"
    assert report.filled_at  # non-empty ISO timestamp


async def test_paper_fill_sell_side() -> None:
    async def fake_price(ticker: str, asset_type: str) -> float:
        return 50.25

    adapter = PaperExecutionAdapter(price_fetch_fn=fake_price)
    order = Order(ticker="ETH", asset_type="eth", side=OrderSide.SELL, quantity=1.5)
    report = await adapter.submit(order)
    assert report.side == "SELL" and report.fill_price == 50.25
