"""Tests for Sprint 12.3: Export System.

Tests portfolio CSV, trade journal CSV, JSON report, signals CSV, alerts CSV,
and content-type correctness.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
from pathlib import Path

import aiosqlite
import pytest

from db.database import init_db
from export.portfolio_report import ExportResult, PortfolioExporter
from monitoring.models import Alert
from monitoring.store import AlertStore
from portfolio.manager import PortfolioManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _setup_db(db_file: Path) -> str:
    """Initialize database and return its path as a string."""
    path = str(db_file)
    await init_db(path)
    return path


async def _add_positions(db_path: str) -> None:
    """Insert a couple of open positions for testing."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position(
        "AAPL", "stock", 100.0, 150.0, "2026-01-10", sector="Technology",
    )
    await mgr.add_position(
        "MSFT", "stock", 50.0, 400.0, "2026-02-01", sector="Technology",
    )


async def _add_and_close_position(db_path: str) -> None:
    """Insert a position and close it (for trade journal tests)."""
    mgr = PortfolioManager(db_path)
    await mgr.add_position("GOOG", "stock", 25.0, 180.0, "2026-01-01")
    await mgr.close_position(
        "GOOG", exit_price=210.0, exit_reason="target_hit", exit_date="2026-03-01",
    )


async def _insert_signals(db_path: str) -> None:
    """Insert rows into signal_history directly."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO signal_history
                (ticker, asset_type, final_signal, final_confidence,
                 raw_score, consensus_score, agent_signals_json,
                 reasoning)
            VALUES
                ('AAPL', 'stock', 'BUY', 0.75, 0.45, 0.80, '[]', 'Strong buy'),
                ('MSFT', 'stock', 'HOLD', 0.55, 0.10, 0.50, '[]', 'Neutral outlook')
            """
        )
        await conn.commit()


async def _insert_alerts(db_path: str) -> None:
    """Insert alerts via AlertStore."""
    store = AlertStore(db_path)
    await store.save_alerts([
        Alert(
            ticker="AAPL",
            alert_type="SIGNIFICANT_LOSS",
            severity="WARNING",
            message="AAPL dropped 5%",
            recommended_action="Review position",
            current_price=142.0,
            trigger_price=150.0,
        ),
        Alert(
            ticker="MSFT",
            alert_type="STOP_LOSS_HIT",
            severity="CRITICAL",
            message="MSFT hit stop loss",
            recommended_action="Consider selling",
            current_price=380.0,
            trigger_price=390.0,
        ),
    ])


def _parse_csv(content: bytes) -> list[list[str]]:
    """Parse CSV bytes into a list of rows (each row is a list of strings)."""
    text = content.decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    return list(reader)


# ---------------------------------------------------------------------------
# 1. Portfolio CSV
# ---------------------------------------------------------------------------

def test_export_portfolio_csv(tmp_path: Path) -> None:
    async def _run() -> None:
        db_path = await _setup_db(tmp_path / "portfolio.db")
        await _add_positions(db_path)

        exporter = PortfolioExporter(db_path)
        result = await exporter.export_portfolio_csv()

        assert result.content_type == "text/csv"
        assert result.filename.startswith("portfolio_")
        assert result.filename.endswith(".csv")

        rows = _parse_csv(result.content)
        # Header row + 2 data rows
        assert len(rows) == 3

        headers = rows[0]
        assert "Ticker" in headers
        assert "Avg Cost" in headers
        assert "Unrealized P&L" in headers
        assert "Status" in headers

        tickers = [row[0] for row in rows[1:]]
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 2. Portfolio CSV empty
# ---------------------------------------------------------------------------

def test_export_portfolio_csv_empty(tmp_path: Path) -> None:
    async def _run() -> None:
        db_path = await _setup_db(tmp_path / "empty.db")

        exporter = PortfolioExporter(db_path)
        result = await exporter.export_portfolio_csv()

        rows = _parse_csv(result.content)
        # Only header row, no data
        assert len(rows) == 1
        assert "Ticker" in rows[0]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 3. Closed positions CSV (trade journal)
# ---------------------------------------------------------------------------

def test_export_closed_positions_csv(tmp_path: Path) -> None:
    async def _run() -> None:
        db_path = await _setup_db(tmp_path / "trades.db")
        await _add_and_close_position(db_path)

        exporter = PortfolioExporter(db_path)
        result = await exporter.export_closed_positions_csv()

        assert result.content_type == "text/csv"
        assert result.filename.startswith("trade_journal_")

        rows = _parse_csv(result.content)
        # Header + 1 closed position
        assert len(rows) == 2

        headers = rows[0]
        assert "Ticker" in headers
        assert "Exit Price" in headers
        assert "Realized P&L" in headers
        assert "Return %" in headers
        assert "Hold Days" in headers

        data = rows[1]
        ticker_idx = headers.index("Ticker")
        assert data[ticker_idx] == "GOOG"

        exit_price_idx = headers.index("Exit Price")
        assert float(data[exit_price_idx]) == 210.0

        pnl_idx = headers.index("Realized P&L")
        assert float(data[pnl_idx]) == 750.0  # (210-180)*25

        reason_idx = headers.index("Exit Reason")
        assert data[reason_idx] == "target_hit"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 4. Portfolio report JSON
# ---------------------------------------------------------------------------

def test_export_portfolio_report_json(tmp_path: Path) -> None:
    async def _run() -> None:
        db_path = await _setup_db(tmp_path / "report.db")
        await _add_positions(db_path)
        await _insert_alerts(db_path)

        exporter = PortfolioExporter(db_path)
        result = await exporter.export_portfolio_report_json()

        assert result.content_type == "application/json"
        assert result.filename.startswith("portfolio_report_")
        assert result.filename.endswith(".json")

        report = json.loads(result.content.decode("utf-8"))

        # Metadata
        assert "metadata" in report
        assert "generated_at" in report["metadata"]
        assert report["metadata"]["version"] == "1.0.0"

        # Summary
        assert "summary" in report
        assert "total_value" in report["summary"]
        assert "num_open_positions" in report["summary"]
        assert report["summary"]["num_open_positions"] == 2

        # Positions
        assert "positions" in report
        assert len(report["positions"]) == 2
        tickers = [p["ticker"] for p in report["positions"]]
        assert "AAPL" in tickers
        assert "MSFT" in tickers

        # Closed positions (none added)
        assert "closed_positions" in report

        # Recent alerts
        assert "recent_alerts" in report
        assert len(report["recent_alerts"]) == 2

        # Recent signals
        assert "recent_signals" in report

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 5. Signals CSV
# ---------------------------------------------------------------------------

def test_export_signals_csv(tmp_path: Path) -> None:
    async def _run() -> None:
        db_path = await _setup_db(tmp_path / "signals.db")
        await _insert_signals(db_path)

        exporter = PortfolioExporter(db_path)
        result = await exporter.export_signals_csv()

        assert result.content_type == "text/csv"
        assert "signals" in result.filename

        rows = _parse_csv(result.content)
        # Header + 2 signal rows
        assert len(rows) == 3

        headers = rows[0]
        assert "Ticker" in headers
        assert "Signal" in headers
        assert "Confidence" in headers
        assert "Raw Score" in headers
        assert "Consensus" in headers
        assert "Regime" in headers

        tickers = [row[headers.index("Ticker")] for row in rows[1:]]
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    asyncio.run(_run())


def test_export_signals_csv_filtered(tmp_path: Path) -> None:
    """Export signals for a specific ticker only."""
    async def _run() -> None:
        db_path = await _setup_db(tmp_path / "signals_filter.db")
        await _insert_signals(db_path)

        exporter = PortfolioExporter(db_path)
        result = await exporter.export_signals_csv(ticker="AAPL")

        rows = _parse_csv(result.content)
        # Header + 1 matching row
        assert len(rows) == 2
        headers = rows[0]
        assert rows[1][headers.index("Ticker")] == "AAPL"
        assert "AAPL" in result.filename

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 6. Alerts CSV
# ---------------------------------------------------------------------------

def test_export_alerts_csv(tmp_path: Path) -> None:
    async def _run() -> None:
        db_path = await _setup_db(tmp_path / "alerts.db")
        await _insert_alerts(db_path)

        exporter = PortfolioExporter(db_path)
        result = await exporter.export_alerts_csv()

        assert result.content_type == "text/csv"
        assert "alerts" in result.filename

        rows = _parse_csv(result.content)
        # Header + 2 alert rows
        assert len(rows) == 3

        headers = rows[0]
        assert "Ticker" in headers
        assert "Type" in headers
        assert "Severity" in headers
        assert "Message" in headers
        assert "Acknowledged" in headers

        tickers = [row[headers.index("Ticker")] for row in rows[1:]]
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 7. Content-type correctness
# ---------------------------------------------------------------------------

def test_export_result_content_types(tmp_path: Path) -> None:
    async def _run() -> None:
        db_path = await _setup_db(tmp_path / "types.db")

        exporter = PortfolioExporter(db_path)

        csv_result = await exporter.export_portfolio_csv()
        assert csv_result.content_type == "text/csv"

        trades_result = await exporter.export_closed_positions_csv()
        assert trades_result.content_type == "text/csv"

        signals_result = await exporter.export_signals_csv()
        assert signals_result.content_type == "text/csv"

        alerts_result = await exporter.export_alerts_csv()
        assert alerts_result.content_type == "text/csv"

        json_result = await exporter.export_portfolio_report_json()
        assert json_result.content_type == "application/json"

    asyncio.run(_run())
