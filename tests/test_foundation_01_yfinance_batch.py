"""Tests for YFinanceProvider.get_price_history_batch (FOUND-01).

Covers behaviors A-G from the plan:
A - Returns dict[str, pd.DataFrame] with correct keys and OHLCV columns
B - Invokes yf.download exactly ONCE for N-ticker list, with group_by="ticker"
C - Empty ticker list raises ValueError
D - MultiIndex DataFrame splits correctly per ticker
E - Empty DataFrame for a ticker yields empty DataFrame with OHLCV cols, NOT missing key
F - Single-ticker get_price_history still works unchanged (regression)
G - _yfinance_lock is still present in the module (grep check)
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data_providers.yfinance_provider import YFinanceProvider, _yfinance_lock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_COLS = ["Open", "High", "Low", "Close", "Volume"]


def _make_multiindex_df(tickers: list[str], rows: int = 5) -> pd.DataFrame:
    """Build a fake yf.download MultiIndex DataFrame for group_by='ticker'.

    yfinance returns a MultiIndex where level 0 = ticker, level 1 = price type.
    Example columns: (AAPL, Open), (AAPL, High), ..., (MSFT, Open), ...
    """
    import numpy as np

    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    arrays = [
        # level 0: ticker repeated for each price column
        [t for t in tickers for _ in EXPECTED_COLS + ["Adj Close"]],
        # level 1: price type repeated for each ticker
        (EXPECTED_COLS + ["Adj Close"]) * len(tickers),
    ]
    columns = pd.MultiIndex.from_arrays(arrays)
    data = {col: [float(i + 1) for i in range(rows)] for col in columns}
    return pd.DataFrame(data, index=index)


def _make_single_ticker_flat_df(rows: int = 5) -> pd.DataFrame:
    """Flat (non-MultiIndex) df as returned by yfinance for a single ticker."""
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "open": [1.0] * rows,
            "high": [2.0] * rows,
            "low": [0.5] * rows,
            "close": [1.5] * rows,
            "volume": [1_000.0] * rows,
            "adj close": [1.5] * rows,
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# Test A: dict return with correct keys and OHLCV columns
# ---------------------------------------------------------------------------

def test_batch_returns_dict_with_correct_keys_and_columns() -> None:
    """Behavior A: returns dict[str, pd.DataFrame] with expected keys + cols."""
    tickers = ["AAPL", "MSFT"]
    fake_raw = _make_multiindex_df(tickers)

    with patch("data_providers.yfinance_provider.yf.download", return_value=fake_raw):
        result = asyncio.run(
            YFinanceProvider().get_price_history_batch(tickers, period="1mo", interval="1d")
        )

    assert isinstance(result, dict), "Result must be a dict"
    assert set(result.keys()) == set(tickers), "Keys must match requested tickers"
    for ticker, df in result.items():
        assert isinstance(df, pd.DataFrame), f"{ticker} value must be DataFrame"
        for col in EXPECTED_COLS:
            assert col in df.columns, f"{ticker} missing column {col}"


# ---------------------------------------------------------------------------
# Test B: yf.download called exactly once with required kwargs
# ---------------------------------------------------------------------------

def test_batch_calls_yf_download_exactly_once_with_group_by() -> None:
    """Behavior B: exactly one yf.download call with group_by='ticker'."""
    tickers = [f"T{i}" for i in range(10)]
    fake_raw = _make_multiindex_df(tickers)

    with patch("data_providers.yfinance_provider.yf.download", return_value=fake_raw) as mock_dl:
        asyncio.run(
            YFinanceProvider().get_price_history_batch(tickers, period="1y", interval="1d")
        )

    mock_dl.assert_called_once()
    call_kwargs = mock_dl.call_args.kwargs if mock_dl.call_args.kwargs else {}
    call_args = mock_dl.call_args.args if mock_dl.call_args.args else ()

    # Check group_by="ticker" is in kwargs
    assert call_kwargs.get("group_by") == "ticker", (
        f"Expected group_by='ticker', got: {call_kwargs}"
    )
    assert call_kwargs.get("progress") is False, "progress must be False"
    assert call_kwargs.get("threads") is True, "threads must be True"


# ---------------------------------------------------------------------------
# Test C: Empty ticker list raises ValueError
# ---------------------------------------------------------------------------

def test_batch_empty_tickers_raises_value_error() -> None:
    """Behavior C: empty ticker list raises ValueError."""
    with pytest.raises(ValueError, match="tickers must be non-empty"):
        asyncio.run(YFinanceProvider().get_price_history_batch([]))


# ---------------------------------------------------------------------------
# Test D: MultiIndex DataFrame splits correctly per ticker
# ---------------------------------------------------------------------------

def test_batch_splits_multiindex_correctly() -> None:
    """Behavior D: MultiIndex result splits into per-ticker dicts."""
    tickers = ["AAPL", "MSFT", "GOOGL"]
    fake_raw = _make_multiindex_df(tickers, rows=3)

    with patch("data_providers.yfinance_provider.yf.download", return_value=fake_raw):
        result = asyncio.run(
            YFinanceProvider().get_price_history_batch(tickers, period="1mo", interval="1d")
        )

    assert len(result) == 3
    for t in tickers:
        assert t in result
        df = result[t]
        assert list(df.columns) == EXPECTED_COLS
        assert len(df) == 3  # 3 rows, none dropped because data is valid


# ---------------------------------------------------------------------------
# Test E: One ticker returns empty -> yields empty DF with expected cols (not missing key)
# ---------------------------------------------------------------------------

def test_batch_missing_ticker_yields_empty_df_with_columns() -> None:
    """Behavior E: ticker missing from batch result -> empty DF with OHLCV cols."""
    present = ["AAPL"]
    missing = "MSFT"
    tickers = [present[0], missing]

    # Only AAPL in the MultiIndex — MSFT is absent
    fake_raw = _make_multiindex_df(present, rows=5)

    with patch("data_providers.yfinance_provider.yf.download", return_value=fake_raw):
        result = asyncio.run(
            YFinanceProvider().get_price_history_batch(tickers, period="1mo", interval="1d")
        )

    assert missing in result, "Missing ticker must still be a key in result"
    df = result[missing]
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    for col in EXPECTED_COLS:
        assert col in df.columns, f"Empty DF must still have column {col}"


# ---------------------------------------------------------------------------
# Test F: Single-ticker get_price_history (regression)
# ---------------------------------------------------------------------------

def test_single_ticker_get_price_history_regression() -> None:
    """Behavior F: existing single-ticker get_price_history still works."""
    rows = 5
    fake_single = pd.DataFrame(
        {
            "Open": [1.0] * rows,
            "High": [2.0] * rows,
            "Low": [0.5] * rows,
            "Close": [1.5] * rows,
            "Volume": [1000.0] * rows,
        },
        index=pd.date_range("2024-01-01", periods=rows),
    )

    with patch("data_providers.yfinance_provider.yf.download", return_value=fake_single):
        result = asyncio.run(
            YFinanceProvider().get_price_history("AAPL", period="5d", interval="1d")
        )

    assert isinstance(result, pd.DataFrame)
    for col in EXPECTED_COLS:
        assert col in result.columns


# ---------------------------------------------------------------------------
# Test G: _yfinance_lock is still in the module (grep-style check)
# ---------------------------------------------------------------------------

def test_yfinance_lock_still_present_in_module() -> None:
    """Behavior G: _yfinance_lock = threading.Lock() still in the source file."""
    import threading

    source_path = Path("data_providers/yfinance_provider.py")
    assert source_path.exists(), "yfinance_provider.py not found"
    content = source_path.read_text(encoding="utf-8")
    assert "_yfinance_lock" in content, "_yfinance_lock removed from module"
    assert "threading.Lock()" in content, "threading.Lock() removed from module"
    # threading.Lock() returns an instance of _thread.lock (an internal C type).
    # We verify by checking the type name rather than isinstance(), because
    # threading.Lock is a factory function, not a class.
    assert "lock" in type(_yfinance_lock).__name__.lower(), (
        f"_yfinance_lock must be a threading lock; got {type(_yfinance_lock)}"
    )
