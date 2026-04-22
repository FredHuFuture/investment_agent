"""Tests for benchmark allowlist enforcement (Threat T-04-03 SSRF mitigation).

Verifies that GET /analytics/benchmark rejects off-allowlist tickers with HTTP 400
and accepts all 5 valid benchmarks (SPY, QQQ, TLT, GLD, BTC-USD) with uppercase
normalization.

All tests use asyncio_mode=auto; no asyncio.run() wrappers.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from api.app import create_app
from db.database import init_db
from engine.analytics import VALID_BENCHMARKS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "test_allowlist.db")
    await init_db(path)
    return path


@pytest.fixture
async def client(db_path: str) -> httpx.AsyncClient:
    app = create_app(db_path=db_path)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# 1. VALID_BENCHMARKS constant integrity
# ---------------------------------------------------------------------------


def test_constants_immutable() -> None:
    """VALID_BENCHMARKS must be a frozenset containing exactly the 5 allowed tickers."""
    assert isinstance(VALID_BENCHMARKS, frozenset)
    assert VALID_BENCHMARKS == {"SPY", "QQQ", "TLT", "GLD", "BTC-USD"}


# ---------------------------------------------------------------------------
# 2. Off-allowlist tickers → HTTP 400
# ---------------------------------------------------------------------------


async def test_off_allowlist_ticker_rejected_foo(client: httpx.AsyncClient) -> None:
    """Arbitrary unknown ticker returns 400."""
    resp = await client.get("/analytics/benchmark?benchmark=FOO")
    assert resp.status_code == 400
    body = resp.json()
    assert "Unknown benchmark" in body.get("detail", "")


async def test_off_allowlist_ticker_rejected_path_traversal(
    client: httpx.AsyncClient,
) -> None:
    """Path traversal attempt ../etc/passwd returns 400."""
    resp = await client.get("/analytics/benchmark?benchmark=../etc/passwd")
    assert resp.status_code == 400
    body = resp.json()
    assert "Unknown benchmark" in body.get("detail", "")


async def test_off_allowlist_ticker_rejected_sql_injection(
    client: httpx.AsyncClient,
) -> None:
    """SQL injection attempt returns 400."""
    resp = await client.get("/analytics/benchmark?benchmark=SPY;%20DROP%20TABLE%20active_positions")
    assert resp.status_code == 400
    body = resp.json()
    assert "Unknown benchmark" in body.get("detail", "")


async def test_off_allowlist_ticker_rejected_msft(client: httpx.AsyncClient) -> None:
    """Legitimate but non-benchmark ticker returns 400."""
    resp = await client.get("/analytics/benchmark?benchmark=MSFT")
    assert resp.status_code == 400


async def test_off_allowlist_ticker_rejected_url(client: httpx.AsyncClient) -> None:
    """URL-style SSRF attempt returns 400."""
    resp = await client.get("/analytics/benchmark?benchmark=http://evil.example.com")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 3. Uppercase normalization — lowercase input accepted
# ---------------------------------------------------------------------------


async def test_allowlist_ticker_accepted_lowercase_spy(
    client: httpx.AsyncClient,
) -> None:
    """Lowercase 'spy' is normalized to 'SPY' and passes the allowlist check.

    The endpoint may still return non-200 due to no portfolio snapshots or
    network issues, but it must NOT return 400 (allowlist rejection).
    """
    from unittest.mock import AsyncMock, patch

    import pandas as pd
    from datetime import datetime

    dates = pd.date_range(end=datetime.now(), periods=10, freq="B")
    mock_df = pd.DataFrame(
        {"Close": [450.0] * 10},
        index=dates,
    )
    mock_provider = AsyncMock()
    mock_provider.get_price_history = AsyncMock(return_value=mock_df)

    with patch("data_providers.factory.get_provider", return_value=mock_provider):
        resp = await client.get("/analytics/benchmark?benchmark=spy")

    # Must NOT be 400 (allowlist rejection)
    assert resp.status_code != 400, (
        f"lowercase 'spy' should be accepted after normalization, got {resp.status_code}"
    )


async def test_allowlist_ticker_accepted_lowercase_qqq(
    client: httpx.AsyncClient,
) -> None:
    """Lowercase 'qqq' is normalized to 'QQQ' and passes the allowlist check."""
    from unittest.mock import AsyncMock, patch

    import pandas as pd
    from datetime import datetime

    dates = pd.date_range(end=datetime.now(), periods=10, freq="B")
    mock_df = pd.DataFrame(
        {"Close": [380.0] * 10},
        index=dates,
    )
    mock_provider = AsyncMock()
    mock_provider.get_price_history = AsyncMock(return_value=mock_df)

    with patch("data_providers.factory.get_provider", return_value=mock_provider):
        resp = await client.get("/analytics/benchmark?benchmark=qqq")

    assert resp.status_code != 400


# ---------------------------------------------------------------------------
# 4. All 5 valid benchmarks pass the allowlist check (mocked provider)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticker", ["SPY", "QQQ", "TLT", "GLD", "BTC-USD"])
async def test_each_valid_benchmark_not_rejected(
    client: httpx.AsyncClient, ticker: str
) -> None:
    """Each allowlisted benchmark must not return HTTP 400."""
    from unittest.mock import AsyncMock, patch

    import pandas as pd
    from datetime import datetime

    dates = pd.date_range(end=datetime.now(), periods=10, freq="B")
    mock_df = pd.DataFrame({"Close": [100.0] * 10}, index=dates)
    mock_provider = AsyncMock()
    mock_provider.get_price_history = AsyncMock(return_value=mock_df)

    with patch("data_providers.factory.get_provider", return_value=mock_provider):
        resp = await client.get(f"/analytics/benchmark?benchmark={ticker}")

    assert resp.status_code != 400, (
        f"Valid benchmark {ticker!r} must not be rejected with 400"
    )
