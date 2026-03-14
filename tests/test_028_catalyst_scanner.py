"""Tests for Sprint 10.4: Catalyst Scanner (run_catalyst_scan).

All tests use tmp_path DBs and mock external I/O -- no real API calls, no network.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from agents.models import AgentOutput, Signal
from daemon.jobs import run_catalyst_scan
from db.database import init_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _null_logger() -> logging.Logger:
    """Logger that discards all output."""
    logger = logging.getLogger(f"test_catalyst_{id(object())}")
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


async def _insert_position(
    db_path: str,
    ticker: str,
    asset_type: str = "stock",
    quantity: float = 10.0,
    avg_cost: float = 100.0,
) -> None:
    """Insert a minimal open position into active_positions."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """
            INSERT INTO active_positions (
                ticker, asset_type, quantity, avg_cost, entry_date
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (ticker, asset_type, quantity, avg_cost, "2024-01-01"),
        )
        await conn.commit()


def _make_agent_output(
    ticker: str = "AAPL",
    signal: Signal = Signal.HOLD,
    confidence: float = 50.0,
    reasoning: str = "Mock reasoning for test",
) -> AgentOutput:
    """Create a mock AgentOutput."""
    return AgentOutput(
        agent_name="SentimentAgent",
        ticker=ticker,
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        metrics={"sentiment_score": 0.5, "catalyst_count": 2, "headline_count": 5},
    )


# ---------------------------------------------------------------------------
# 1. No positions -> skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalyst_scan_no_positions(tmp_path: Path) -> None:
    """Empty portfolio returns skipped status."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    result = await run_catalyst_scan(db_path, logger)

    assert result["status"] == "skipped"
    assert "No open positions" in result["reason"]

    # Verify daemon_runs row
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT job_name, status FROM daemon_runs WHERE job_name = 'catalyst_scan'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "catalyst_scan"
    assert row[1] == "skipped"


# ---------------------------------------------------------------------------
# 2. SELL signal with high confidence -> alert created
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalyst_scan_with_sell_signal(tmp_path: Path) -> None:
    """Mock SentimentAgent returning SELL for a long position -- verify alert is created."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    await _insert_position(db_path, "AAPL", "stock")

    sell_output = _make_agent_output(
        ticker="AAPL",
        signal=Signal.SELL,
        confidence=78.0,
        reasoning="Negative earnings surprise and SEC investigation reported",
    )

    with patch("agents.sentiment.SentimentAgent") as MockSentimentAgent, \
         patch("data_providers.web_news_provider.WebNewsProvider"), \
         patch("data_providers.yfinance_provider.YFinanceProvider"):

        mock_agent = MockSentimentAgent.return_value
        mock_agent.analyze = AsyncMock(return_value=sell_output)

        result = await run_catalyst_scan(db_path, logger)

    assert result["status"] == "success"
    assert result["positions_scanned"] == 1
    assert result["alerts_created"] == 1

    # Verify the alert was saved
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT alert_type, severity, ticker, message FROM monitoring_alerts WHERE ticker = 'AAPL'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "CATALYST"
    assert row[1] == "CRITICAL"  # confidence >= 75 -> CRITICAL
    assert row[2] == "AAPL"
    assert "SELL" in row[3]
    assert "78%" in row[3]


# ---------------------------------------------------------------------------
# 3. SELL signal with LOW confidence -> no alert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalyst_scan_low_confidence_no_alert(tmp_path: Path) -> None:
    """Mock SELL with confidence 40 -- verify NO alert created."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    await _insert_position(db_path, "MSFT", "stock")

    low_confidence_sell = _make_agent_output(
        ticker="MSFT",
        signal=Signal.SELL,
        confidence=40.0,
        reasoning="Slightly negative sentiment but unclear direction",
    )

    with patch("agents.sentiment.SentimentAgent") as MockSentimentAgent, \
         patch("data_providers.web_news_provider.WebNewsProvider"), \
         patch("data_providers.yfinance_provider.YFinanceProvider"):

        mock_agent = MockSentimentAgent.return_value
        mock_agent.analyze = AsyncMock(return_value=low_confidence_sell)

        result = await run_catalyst_scan(db_path, logger)

    assert result["status"] == "success"
    assert result["positions_scanned"] == 1
    assert result["alerts_created"] == 0

    # Verify no alert was saved
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT COUNT(*) FROM monitoring_alerts WHERE ticker = 'MSFT'"
            )
        ).fetchone()
    assert row[0] == 0


# ---------------------------------------------------------------------------
# 4. Verify daemon_runs table gets a row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalyst_scan_records_daemon_run(tmp_path: Path) -> None:
    """Verify daemon_runs table gets a row after a successful scan."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    await _insert_position(db_path, "GOOG", "stock")

    hold_output = _make_agent_output(
        ticker="GOOG",
        signal=Signal.HOLD,
        confidence=55.0,
        reasoning="Mixed sentiment, no clear catalyst",
    )

    with patch("agents.sentiment.SentimentAgent") as MockSentimentAgent, \
         patch("data_providers.web_news_provider.WebNewsProvider"), \
         patch("data_providers.yfinance_provider.YFinanceProvider"):

        mock_agent = MockSentimentAgent.return_value
        mock_agent.analyze = AsyncMock(return_value=hold_output)

        result = await run_catalyst_scan(db_path, logger)

    assert result["status"] == "success"

    # Verify daemon_runs row
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT job_name, status, result_json, duration_ms FROM daemon_runs WHERE job_name = 'catalyst_scan'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "catalyst_scan"
    assert row[1] == "success"
    assert row[3] >= 0  # duration_ms is non-negative

    result_data = json.loads(row[2])
    assert result_data["positions_scanned"] == 1
    assert result_data["alerts_created"] == 0


# ---------------------------------------------------------------------------
# 5. SentimentAgent.analyze raises exception -> scan continues (no crash)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalyst_scan_handles_agent_error(tmp_path: Path) -> None:
    """Mock SentimentAgent.analyze raising exception -- verify scan continues."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    logger = _null_logger()

    # Insert two positions
    await _insert_position(db_path, "AAPL", "stock")
    await _insert_position(db_path, "MSFT", "stock")

    hold_output = _make_agent_output(
        ticker="MSFT",
        signal=Signal.HOLD,
        confidence=50.0,
    )

    call_count = [0]

    async def _analyze_side_effect(agent_input):
        call_count[0] += 1
        if agent_input.ticker == "AAPL":
            raise RuntimeError("API rate limit exceeded")
        return hold_output

    with patch("agents.sentiment.SentimentAgent") as MockSentimentAgent, \
         patch("data_providers.web_news_provider.WebNewsProvider"), \
         patch("data_providers.yfinance_provider.YFinanceProvider"):

        mock_agent = MockSentimentAgent.return_value
        mock_agent.analyze = AsyncMock(side_effect=_analyze_side_effect)

        result = await run_catalyst_scan(db_path, logger)

    # AAPL failed, MSFT succeeded
    assert result["status"] == "success"
    assert result["positions_scanned"] == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["ticker"] == "AAPL"
    assert "rate limit" in result["errors"][0]["error"]

    # Verify daemon_runs row still records success (partial success is still success)
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                "SELECT status FROM daemon_runs WHERE job_name = 'catalyst_scan'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "success"
