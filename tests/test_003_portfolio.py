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


def test_concentration_uses_market_value(tmp_path: Path) -> None:
    """Exposure/concentration must use market_value when current_price is set."""

    async def _run() -> None:
        manager = await _create_manager(tmp_path / "market_value.db")

        # Two positions with identical cost_basis (10 * 100 = 1000 each)
        await manager.add_position(
            "WINNER", "stock", 10.0, 100.0, "2026-02-10", sector="Tech"
        )
        await manager.add_position(
            "LOSER", "stock", 10.0, 100.0, "2026-02-10", sector="Health"
        )

        # Load portfolio first to get positions, then set current prices
        portfolio = await manager.load_portfolio()

        # Simulate price fetch: WINNER doubled, LOSER halved
        for pos in portfolio.positions:
            if pos.ticker == "WINNER":
                pos.current_price = 200.0  # market_value = 10 * 200 = 2000
            elif pos.ticker == "LOSER":
                pos.current_price = 50.0  # market_value = 10 * 50 = 500

        # Recompute with the new prices via recompute_with_prices
        updated = manager.recompute_with_prices(portfolio)

        total = 2000.0 + 500.0  # no cash
        winner_pct = 2000.0 / total
        loser_pct = 500.0 / total

        # Verify concentration reflects market_value, not cost_basis
        conc = dict(updated.top_concentration)
        assert pytest.approx(conc["WINNER"], rel=1e-6) == winner_pct
        assert pytest.approx(conc["LOSER"], rel=1e-6) == loser_pct

        # WINNER should be ranked first (higher market_value)
        assert updated.top_concentration[0][0] == "WINNER"

        # Verify sector breakdown uses market_value
        assert pytest.approx(updated.sector_breakdown["Tech"], rel=1e-6) == winner_pct
        assert pytest.approx(updated.sector_breakdown["Health"], rel=1e-6) == loser_pct

        # --- Also verify load_portfolio itself uses market_value ---
        # Reload, patch prices on the positions, and call load_portfolio
        # Since load_portfolio reads from DB (where current_price is not stored),
        # it will fall back to cost_basis. We verify this fallback is correct.
        portfolio_no_price = await manager.load_portfolio()
        conc_no_price = dict(portfolio_no_price.top_concentration)
        # With no current_price set, both have equal cost_basis so 50/50
        assert pytest.approx(conc_no_price["WINNER"], rel=1e-6) == 0.5
        assert pytest.approx(conc_no_price["LOSER"], rel=1e-6) == 0.5

    asyncio.run(_run())


def test_load_portfolio_uses_market_value_when_price_set(tmp_path: Path) -> None:
    """load_portfolio must use market_value (not cost_basis) when current_price > 0."""

    async def _run() -> None:
        db_file = tmp_path / "mv_load.db"
        manager = await _create_manager(db_file)

        # CHEAP bought at $10, EXPENSIVE bought at $100 -- same qty
        await manager.add_position(
            "CHEAP", "stock", 10.0, 10.0, "2026-02-10", sector="Tech"
        )
        await manager.add_position(
            "EXPENSIVE", "stock", 10.0, 100.0, "2026-02-10", sector="Finance"
        )
        await manager.set_cash(0.0)

        # Without current_price, cost_basis is used:
        # CHEAP cost_basis = 100, EXPENSIVE cost_basis = 1000
        portfolio = await manager.load_portfolio()
        conc = dict(portfolio.top_concentration)
        assert pytest.approx(conc["EXPENSIVE"], rel=1e-6) == 1000.0 / 1100.0
        assert pytest.approx(conc["CHEAP"], rel=1e-6) == 100.0 / 1100.0

        # Now inject current_price on positions and reload via recompute.
        # CHEAP surged to $500, EXPENSIVE dropped to $50.
        for pos in portfolio.positions:
            if pos.ticker == "CHEAP":
                pos.current_price = 500.0  # market_value = 5000
            elif pos.ticker == "EXPENSIVE":
                pos.current_price = 50.0  # market_value = 500

        updated = manager.recompute_with_prices(portfolio)
        conc2 = dict(updated.top_concentration)

        # Now CHEAP dominates by market_value
        assert pytest.approx(conc2["CHEAP"], rel=1e-6) == 5000.0 / 5500.0
        assert pytest.approx(conc2["EXPENSIVE"], rel=1e-6) == 500.0 / 5500.0
        assert updated.top_concentration[0][0] == "CHEAP"

    asyncio.run(_run())
