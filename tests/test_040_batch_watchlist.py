"""Tests for Sprint 14.3: Batch Watchlist Analysis.

Covers the POST /watchlist/analyze-all endpoint: empty watchlist, successful
batch analysis, partial failures, update_analysis calls, and summary counts.
All tests use a temp SQLite DB and mock the pipeline -- no network calls.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from agents.models import AgentOutput, Signal
from api.app import create_app
from db.database import init_db
from engine.aggregator import AggregatedSignal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_batch_wl.db")
    await init_db(path)
    return path


@pytest.fixture
async def client(db_path: str):
    app = create_app(db_path=db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_aggregated_signal(ticker: str = "AAPL", signal: Signal = Signal.BUY, confidence: float = 72.0) -> AggregatedSignal:
    return AggregatedSignal(
        ticker=ticker,
        asset_type="stock",
        final_signal=signal,
        final_confidence=confidence,
        regime=None,
        agent_signals=[
            AgentOutput(
                agent_name="TechnicalAgent",
                ticker=ticker,
                signal=signal,
                confidence=confidence,
                reasoning="test",
            ),
        ],
        reasoning=f"Test {signal.value} signal",
        metrics={"raw_score": 0.45, "consensus_score": 1.0},
        warnings=[],
    )


async def _add_ticker(client: httpx.AsyncClient, ticker: str, asset_type: str = "stock") -> None:
    resp = await client.post("/watchlist", json={"ticker": ticker, "asset_type": asset_type})
    assert resp.status_code == 200, f"Failed to add {ticker}: {resp.text}"


# ---------------------------------------------------------------------------
# 1. Batch analyze empty watchlist
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_analyze_empty_watchlist(client: httpx.AsyncClient):
    """POST /watchlist/analyze-all with no tickers returns empty results and a warning."""
    resp = await client.post("/watchlist/analyze-all")
    assert resp.status_code == 200

    body = resp.json()
    data = body["data"]
    assert data["results"] == []
    assert data["total"] == 0
    assert data["success_count"] == 0
    assert len(body["warnings"]) == 1
    assert "empty" in body["warnings"][0].lower()


# ---------------------------------------------------------------------------
# 2. Batch analyze with mock pipeline (all succeed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_analyze_all_succeed(client: httpx.AsyncClient):
    """All tickers succeed when the pipeline is mocked to return valid signals."""
    await _add_ticker(client, "AAPL")
    await _add_ticker(client, "GOOG")
    await _add_ticker(client, "MSFT")

    mock_pipeline = AsyncMock()

    async def _fake_analyze(ticker: str, asset_type: str, **_kw):
        return _mock_aggregated_signal(ticker=ticker)

    mock_pipeline.analyze_ticker = AsyncMock(side_effect=_fake_analyze)

    with patch("engine.pipeline.AnalysisPipeline", return_value=mock_pipeline):
        resp = await client.post("/watchlist/analyze-all")

    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]

    assert data["total"] == 3
    assert data["success_count"] == 3
    assert len(data["results"]) == 3
    assert body["warnings"] == []

    for result in data["results"]:
        assert result["status"] == "success"
        assert result["signal"] == "BUY"
        assert result["confidence"] == 72.0
        assert result["raw_score"] == 0.45


# ---------------------------------------------------------------------------
# 3. Batch analyze with one failure (should continue, report error)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_analyze_partial_failure(client: httpx.AsyncClient):
    """If one ticker fails, the others still succeed and the error is reported."""
    await _add_ticker(client, "AAPL")
    await _add_ticker(client, "BAD_TICKER")
    await _add_ticker(client, "MSFT")

    call_count = 0

    async def _fake_analyze(ticker: str, asset_type: str, **_kw):
        nonlocal call_count
        call_count += 1
        if "BAD" in ticker:
            raise RuntimeError("Data provider error: no data for BAD_TICKER")
        return _mock_aggregated_signal(ticker=ticker)

    mock_pipeline = AsyncMock()
    mock_pipeline.analyze_ticker = AsyncMock(side_effect=_fake_analyze)

    with patch("engine.pipeline.AnalysisPipeline", return_value=mock_pipeline):
        resp = await client.post("/watchlist/analyze-all")

    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]

    assert data["total"] == 3
    assert data["success_count"] == 2
    assert len(data["results"]) == 3

    # Check the failure result
    error_results = [r for r in data["results"] if r["status"] == "error"]
    assert len(error_results) == 1
    assert error_results[0]["ticker"] == "BAD_TICKER"
    assert error_results[0]["signal"] is None
    assert error_results[0]["confidence"] is None
    assert "error" in error_results[0]

    # Check warnings contain the failure
    assert len(body["warnings"]) == 1
    assert "BAD_TICKER" in body["warnings"][0]

    # Pipeline was called for all 3 tickers (didn't bail early)
    assert call_count == 3


# ---------------------------------------------------------------------------
# 4. Verify manager.update_analysis is called for successful results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_updates_analysis_in_db(client: httpx.AsyncClient):
    """After batch analysis, the watchlist items should have updated signals."""
    await _add_ticker(client, "NVDA")
    await _add_ticker(client, "TSLA")

    async def _fake_analyze(ticker: str, asset_type: str, **_kw):
        if ticker == "NVDA":
            return _mock_aggregated_signal(ticker=ticker, signal=Signal.BUY, confidence=80.0)
        return _mock_aggregated_signal(ticker=ticker, signal=Signal.SELL, confidence=65.0)

    mock_pipeline = AsyncMock()
    mock_pipeline.analyze_ticker = AsyncMock(side_effect=_fake_analyze)

    with patch("engine.pipeline.AnalysisPipeline", return_value=mock_pipeline):
        resp = await client.post("/watchlist/analyze-all")
    assert resp.status_code == 200

    # Fetch the watchlist and verify signals were persisted
    resp = await client.get("/watchlist")
    assert resp.status_code == 200
    items = resp.json()["data"]
    by_ticker = {item["ticker"]: item for item in items}

    assert by_ticker["NVDA"]["last_signal"] == "BUY"
    assert by_ticker["NVDA"]["last_confidence"] == 80.0
    assert by_ticker["NVDA"]["last_analysis_at"] is not None

    assert by_ticker["TSLA"]["last_signal"] == "SELL"
    assert by_ticker["TSLA"]["last_confidence"] == 65.0
    assert by_ticker["TSLA"]["last_analysis_at"] is not None


# ---------------------------------------------------------------------------
# 5. Summary counts (total, success_count) with mixed results
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_summary_counts(client: httpx.AsyncClient):
    """Verify total and success_count are correct with a mix of successes and failures."""
    await _add_ticker(client, "AAPL")
    await _add_ticker(client, "FAIL1")
    await _add_ticker(client, "GOOG")
    await _add_ticker(client, "FAIL2")

    async def _fake_analyze(ticker: str, asset_type: str, **_kw):
        if ticker.startswith("FAIL"):
            raise ValueError(f"Cannot analyze {ticker}")
        return _mock_aggregated_signal(ticker=ticker)

    mock_pipeline = AsyncMock()
    mock_pipeline.analyze_ticker = AsyncMock(side_effect=_fake_analyze)

    with patch("engine.pipeline.AnalysisPipeline", return_value=mock_pipeline):
        resp = await client.post("/watchlist/analyze-all")

    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["total"] == 4
    assert data["success_count"] == 2
    assert len(data["results"]) == 4

    success_results = [r for r in data["results"] if r["status"] == "success"]
    error_results = [r for r in data["results"] if r["status"] == "error"]
    assert len(success_results) == 2
    assert len(error_results) == 2


# ---------------------------------------------------------------------------
# 6. Failed tickers do NOT update analysis in DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_tickers_not_updated_in_db(client: httpx.AsyncClient):
    """Tickers that fail analysis should not have their signal updated."""
    await _add_ticker(client, "GOOD")
    await _add_ticker(client, "BROKEN")

    async def _fake_analyze(ticker: str, asset_type: str, **_kw):
        if ticker == "BROKEN":
            raise RuntimeError("Something went wrong")
        return _mock_aggregated_signal(ticker=ticker, signal=Signal.HOLD, confidence=55.0)

    mock_pipeline = AsyncMock()
    mock_pipeline.analyze_ticker = AsyncMock(side_effect=_fake_analyze)

    with patch("engine.pipeline.AnalysisPipeline", return_value=mock_pipeline):
        resp = await client.post("/watchlist/analyze-all")
    assert resp.status_code == 200

    # Verify DB state
    resp = await client.get("/watchlist")
    items = resp.json()["data"]
    by_ticker = {item["ticker"]: item for item in items}

    # GOOD should be updated
    assert by_ticker["GOOD"]["last_signal"] == "HOLD"
    assert by_ticker["GOOD"]["last_confidence"] == 55.0

    # BROKEN should remain un-analyzed
    assert by_ticker["BROKEN"]["last_signal"] is None
    assert by_ticker["BROKEN"]["last_confidence"] is None
    assert by_ticker["BROKEN"]["last_analysis_at"] is None


# ---------------------------------------------------------------------------
# 7. Result includes correct signal enum values (string, not enum)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_result_signal_values_are_strings(client: httpx.AsyncClient):
    """Signals in the response should be string values, not enum representations."""
    await _add_ticker(client, "AMZN")

    async def _fake_analyze(ticker: str, asset_type: str, **_kw):
        return _mock_aggregated_signal(ticker=ticker, signal=Signal.SELL, confidence=60.0)

    mock_pipeline = AsyncMock()
    mock_pipeline.analyze_ticker = AsyncMock(side_effect=_fake_analyze)

    with patch("engine.pipeline.AnalysisPipeline", return_value=mock_pipeline):
        resp = await client.post("/watchlist/analyze-all")

    assert resp.status_code == 200
    result = resp.json()["data"]["results"][0]
    assert result["signal"] == "SELL"
    assert isinstance(result["signal"], str)
    # Ensure it's not something like "Signal.SELL"
    assert "." not in result["signal"]
