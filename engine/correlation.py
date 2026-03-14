from __future__ import annotations

"""Portfolio correlation tracker -- calculates pairwise correlations and flags
concentration risk when assets move together.

Uses daily returns over a configurable lookback window. Pearson correlation
is computed via pandas for each ticker pair.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from data_providers.base import DataProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sprint 11.2 -- Candidate vs. existing-holdings correlation
# ---------------------------------------------------------------------------

@dataclass
class CorrelationResult:
    """Correlation between a candidate ticker and an existing position."""
    ticker: str
    existing_ticker: str
    correlation: float  # Pearson correlation coefficient
    period_days: int
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "existing_ticker": self.existing_ticker,
            "correlation": round(self.correlation, 4),
            "period_days": self.period_days,
            "warning": self.warning,
        }


async def compute_correlations(
    candidate_ticker: str,
    existing_tickers: list[str],
    provider: DataProvider,
    period: str = "6mo",
    threshold: float = 0.80,
) -> list[CorrelationResult]:
    """Compute Pearson correlation between candidate and each existing ticker.

    Returns list of CorrelationResult for all existing tickers, with warning
    set if |correlation| > threshold.
    """
    if not existing_tickers:
        return []

    # Fetch candidate price history
    try:
        candidate_df = await provider.get_price_history(
            candidate_ticker, period=period, interval="1d"
        )
    except Exception as exc:
        logger.warning(
            "Failed to fetch price history for candidate %s: %s",
            candidate_ticker,
            exc,
        )
        return []

    if candidate_df is None or candidate_df.empty or "Close" not in candidate_df.columns:
        logger.warning("No Close data for candidate %s", candidate_ticker)
        return []

    candidate_close = candidate_df["Close"].dropna()

    results: list[CorrelationResult] = []

    for existing_ticker in existing_tickers:
        try:
            existing_df = await provider.get_price_history(
                existing_ticker, period=period, interval="1d"
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch price history for %s: %s", existing_ticker, exc
            )
            continue

        if existing_df is None or existing_df.empty or "Close" not in existing_df.columns:
            logger.warning("No Close data for %s — skipping", existing_ticker)
            continue

        existing_close = existing_df["Close"].dropna()

        # Align by date (inner join on index)
        combined = pd.DataFrame(
            {"candidate": candidate_close, "existing": existing_close}
        ).dropna()

        if len(combined) < 2:
            logger.warning(
                "Insufficient overlapping data between %s and %s — skipping",
                candidate_ticker,
                existing_ticker,
            )
            continue

        # Compute daily returns and Pearson correlation
        returns = combined.pct_change().dropna()

        if len(returns) < 2:
            logger.warning(
                "Insufficient return data between %s and %s — skipping",
                candidate_ticker,
                existing_ticker,
            )
            continue

        correlation = float(returns["candidate"].corr(returns["existing"]))

        if np.isnan(correlation):
            continue

        period_days = len(returns)

        warning: str | None = None
        if abs(correlation) > threshold:
            warning = (
                f"High correlation ({correlation:.2f}) between "
                f"{candidate_ticker} and {existing_ticker} — "
                f"portfolio diversification risk"
            )

        results.append(
            CorrelationResult(
                ticker=candidate_ticker,
                existing_ticker=existing_ticker,
                correlation=correlation,
                period_days=period_days,
                warning=warning,
            )
        )

    # Sort by absolute correlation descending
    results.sort(key=lambda r: abs(r.correlation), reverse=True)
    return results


# ---------------------------------------------------------------------------
# Original pairwise portfolio correlation (pre-Sprint 11.2)
# ---------------------------------------------------------------------------


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
