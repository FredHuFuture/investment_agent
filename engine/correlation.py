from __future__ import annotations

"""Portfolio correlation tracker -- calculates pairwise correlations and flags
concentration risk when assets move together.

Uses daily returns over a configurable lookback window. Pearson correlation
is computed via pandas for each ticker pair.
"""

import asyncio
from typing import Any

import numpy as np
import pandas as pd

from data_providers.base import DataProvider


async def calculate_portfolio_correlations(
    tickers: list[str],
    provider: DataProvider,
    lookback_days: int = 90,
) -> dict[str, Any]:
    """Calculate pairwise correlations for portfolio positions.

    Args:
        tickers: List of ticker symbols in the portfolio.
        provider: DataProvider for fetching price history.
        lookback_days: Number of calendar days of history to use.

    Returns:
        {
            "correlation_matrix": {("AAPL", "MSFT"): 0.85, ...},
            "avg_correlation": 0.72,
            "high_correlation_pairs": [("AAPL", "MSFT", 0.85), ...],
            "concentration_risk": "HIGH" | "MODERATE" | "LOW",
            "warnings": ["AAPL-MSFT correlation 0.85 (>0.70)"]
        }
    """
    if len(tickers) < 2:
        return {
            "correlation_matrix": {},
            "avg_correlation": 0.0,
            "high_correlation_pairs": [],
            "concentration_risk": "LOW",
            "warnings": [],
        }

    # Map lookback_days to a yfinance period string.
    # Use a slightly larger period to ensure enough trading days.
    if lookback_days <= 30:
        period = "2mo"
    elif lookback_days <= 90:
        period = "4mo"
    elif lookback_days <= 180:
        period = "7mo"
    else:
        period = "1y"

    # Fetch price histories in parallel
    async def _fetch_close(ticker: str) -> tuple[str, pd.Series | None]:
        try:
            df = await provider.get_price_history(ticker, period=period, interval="1d")
            if df is not None and not df.empty and "Close" in df.columns:
                close = df["Close"].dropna()
                # Trim to lookback window
                if len(close) > lookback_days:
                    close = close.iloc[-lookback_days:]
                return (ticker, close)
        except Exception:
            pass
        return (ticker, None)

    results = await asyncio.gather(*[_fetch_close(t) for t in tickers])

    # Build a combined DataFrame of daily returns
    close_data: dict[str, pd.Series] = {}
    for ticker, close_series in results:
        if close_series is not None and len(close_series) >= 5:
            close_data[ticker] = close_series

    if len(close_data) < 2:
        warnings = []
        failed = [t for t in tickers if t not in close_data]
        if failed:
            warnings.append(f"Insufficient price data for: {', '.join(failed)}")
        return {
            "correlation_matrix": {},
            "avg_correlation": 0.0,
            "high_correlation_pairs": [],
            "concentration_risk": "LOW",
            "warnings": warnings,
        }

    # Align all series to common dates and compute daily returns
    price_df = pd.DataFrame(close_data)
    returns_df = price_df.pct_change().dropna()

    if len(returns_df) < 5:
        return {
            "correlation_matrix": {},
            "avg_correlation": 0.0,
            "high_correlation_pairs": [],
            "concentration_risk": "LOW",
            "warnings": ["Insufficient overlapping trading days for correlation."],
        }

    # Compute pairwise Pearson correlation
    corr_matrix = returns_df.corr()

    correlation_pairs: dict[tuple[str, str], float] = {}
    high_pairs: list[tuple[str, str, float]] = []
    warnings: list[str] = []
    all_corrs: list[float] = []

    available_tickers = list(close_data.keys())
    for i, t1 in enumerate(available_tickers):
        for j in range(i + 1, len(available_tickers)):
            t2 = available_tickers[j]
            if t1 in corr_matrix.columns and t2 in corr_matrix.columns:
                corr_val = corr_matrix.loc[t1, t2]
                if np.isnan(corr_val):
                    continue
                corr_val = round(float(corr_val), 4)
                correlation_pairs[(t1, t2)] = corr_val
                all_corrs.append(abs(corr_val))
                if abs(corr_val) > 0.70:
                    high_pairs.append((t1, t2, corr_val))
                    warnings.append(
                        f"{t1}-{t2} correlation {corr_val:.2f} (>0.70)"
                    )

    avg_corr = round(float(np.mean(all_corrs)), 4) if all_corrs else 0.0

    if avg_corr > 0.70:
        risk = "HIGH"
    elif avg_corr >= 0.40:
        risk = "MODERATE"
    else:
        risk = "LOW"

    # Add warnings for tickers that failed to fetch
    failed_tickers = [t for t in tickers if t not in close_data]
    if failed_tickers:
        warnings.append(f"Missing price data for: {', '.join(failed_tickers)}")

    return {
        "correlation_matrix": correlation_pairs,
        "avg_correlation": avg_corr,
        "high_correlation_pairs": high_pairs,
        "concentration_risk": risk,
        "warnings": warnings,
    }
