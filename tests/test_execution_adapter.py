from __future__ import annotations

import pytest

from execution.adapter import ExecutionAdapter, ExecutionReport, Order, OrderSide


def test_abc_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        ExecutionAdapter()  # type: ignore[abstract]


def test_order_and_report_construct() -> None:
    order = Order(ticker="AAPL", asset_type="stock", side=OrderSide.BUY, quantity=3.0)
    assert order.side is OrderSide.BUY
    report = ExecutionReport(
        ticker="AAPL", side="BUY", quantity=3.0, fill_price=190.5,
        status="FILLED", venue="PAPER", filled_at="2026-06-24T00:00:00+00:00",
    )
    d = report.to_dict()
    assert d["status"] == "FILLED" and d["venue"] == "PAPER" and d["fill_price"] == 190.5
