from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest

from db.database import init_db
from portfolio.manager import PortfolioManager


async def _create_manager(db_file: Path) -> PortfolioManager:
    await init_db(db_file)
    return PortfolioManager(db_file)


def test_add_and_load_positions(tmp_path: Path) -> None:
    async def _run() -> None:
        manager = await _create_manager(tmp_path / "portfolio.db")
        await manager.add_position(
            "MSFT", "stock", 200.0, 415.50, "2026-02-10", sector="Technology"
        )
        await manager.add_position(
            "AAPL", "stock", 100.0, 178.00, "2026-02-10", sector="Technology"
        )
        await manager.add_position("BTC", "btc", 0.50, 82000.0, "2026-02-10")
        await manager.set_cash(150000.0)

        portfolio = await manager.load_portfolio()
        assert len(portfolio.positions) == 3
        assert portfolio.cash == 150000.0
        exposure_sum = (
            portfolio.stock_exposure_pct
            + portfolio.crypto_exposure_pct
            + portfolio.cash_pct
        )
        assert abs(exposure_sum - 1.0) < 1e-6

    asyncio.run(_run())


def test_concentration_sorting(tmp_path: Path) -> None:
    async def _run() -> None:
        manager = await _create_manager(tmp_path / "concentration.db")
        await manager.add_position("MSFT", "stock", 200.0, 400.0, "2026-02-10")
        await manager.add_position("AAPL", "stock", 100.0, 200.0, "2026-02-10")
        await manager.add_position("BTC", "btc", 0.5, 80000.0, "2026-02-10")

        portfolio = await manager.load_portfolio()
        tickers = [ticker for ticker, _ in portfolio.top_concentration]
        assert tickers[:3] == ["MSFT", "BTC", "AAPL"]

    asyncio.run(_run())


def test_sector_breakdown(tmp_path: Path) -> None:
    async def _run() -> None:
        manager = await _create_manager(tmp_path / "sector.db")
        await manager.add_position(
            "MSFT", "stock", 200.0, 400.0, "2026-02-10", sector="Technology"
        )
        await manager.add_position(
            "AAPL", "stock", 100.0, 200.0, "2026-02-10", sector="Technology"
        )
        await manager.set_cash(100000.0)

        portfolio = await manager.load_portfolio()
        expected = (200.0 * 400.0 + 100.0 * 200.0) / portfolio.total_value
        assert pytest.approx(portfolio.sector_breakdown["Technology"], rel=1e-6) == expected

    asyncio.run(_run())


def test_scale_portfolio(tmp_path: Path) -> None:
    async def _run() -> None:
        manager = await _create_manager(tmp_path / "scale.db")
        await manager.add_position("MSFT", "stock", 10.0, 100.0, "2026-02-10")
        await manager.scale_portfolio(2.0)
        position = await manager.get_position("MSFT")
        assert position is not None
        assert position.quantity == 20.0
        assert position.avg_cost == 100.0

    asyncio.run(_run())


def test_apply_split(tmp_path: Path) -> None:
    async def _run() -> None:
        manager = await _create_manager(tmp_path / "split.db")
        await manager.add_position("AAPL", "stock", 100.0, 178.0, "2026-02-10")
        result = await manager.apply_split("AAPL", 4)
        assert result is True
        position = await manager.get_position("AAPL")
        assert position is not None
        assert position.quantity == 400.0
        assert position.avg_cost == 44.5

    asyncio.run(_run())


def test_remove_position(tmp_path: Path) -> None:
    async def _run() -> None:
        manager = await _create_manager(tmp_path / "remove.db")
        await manager.add_position("MSFT", "stock", 10.0, 100.0, "2026-02-10")
        removed = await manager.remove_position("MSFT")
        assert removed is True
        position = await manager.get_position("MSFT")
        assert position is None
        portfolio = await manager.load_portfolio()
        assert len(portfolio.positions) == 0

    asyncio.run(_run())


def test_duplicate_ticker_raises(tmp_path: Path) -> None:
    async def _run() -> None:
        manager = await _create_manager(tmp_path / "dupe.db")
        await manager.add_position("MSFT", "stock", 10.0, 100.0, "2026-02-10")
        with pytest.raises(ValueError):
            await manager.add_position("MSFT", "stock", 5.0, 110.0, "2026-02-11")

    asyncio.run(_run())


def test_cash_reconciliation_warning(tmp_path: Path) -> None:
    async def _run() -> None:
        db_file = tmp_path / "cash_check.db"
        manager = await _create_manager(db_file)
        await manager.add_position("MSFT", "stock", 1000.0, 100.0, "2026-02-10")
        await manager.set_cash(150000.0)

        async with aiosqlite.connect(db_file) as conn:
            await conn.execute(
                """
                UPDATE portfolio_meta
                SET value = '100000', updated_at = CURRENT_TIMESTAMP
                WHERE key = 'cash'
                """
            )
            await conn.commit()

        warning = await manager.cash_reconciliation_check()
        assert warning is not None

    asyncio.run(_run())
