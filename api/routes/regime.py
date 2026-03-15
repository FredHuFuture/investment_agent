"""Regime detection endpoint."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from api.deps import get_db_path
from engine.regime import RegimeDetector
from engine.regime_history import RegimeHistoryStore

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/current")
async def get_current_regime() -> dict[str, Any]:
    """Return current regime detection with all indicators.

    This endpoint runs the regime detector with whatever macro data is
    available from FRED / VIX.  Price data is not included by default
    (it requires a specific ticker); callers can use the ``/analyze``
    endpoint for ticker-specific regime-aware analysis.
    """
    warnings: list[str] = []
    macro_data: dict[str, Any] = {}

    # Attempt to gather live macro data from FRED + VIX providers
    try:
        from data_providers.fred_provider import FredProvider

        fred = FredProvider()

        # Fed funds rate + trend
        try:
            fed_funds = await fred.get_fed_funds_rate()
            fed_funds = fed_funds.dropna()
            if not fed_funds.empty:
                macro_data["fed_funds_rate"] = float(fed_funds.iloc[-1])
                if len(fed_funds) >= 4:
                    prior = float(fed_funds.iloc[-4])
                    latest = float(fed_funds.iloc[-1])
                    if latest > prior:
                        macro_data["fed_funds_trend"] = "increasing"
                    elif latest < prior:
                        macro_data["fed_funds_trend"] = "decreasing"
                    else:
                        macro_data["fed_funds_trend"] = "stable"
        except Exception as exc:
            warnings.append(f"Fed funds unavailable: {exc}")

        # Treasury yields + spread
        try:
            t10y = await fred.get_treasury_yield("10y")
            t2y = await fred.get_treasury_yield("2y")
            val_10y = float(t10y.dropna().iloc[-1]) if not t10y.empty else None
            val_2y = float(t2y.dropna().iloc[-1]) if not t2y.empty else None
            macro_data["treasury_10y"] = val_10y
            macro_data["treasury_2y"] = val_2y
            if val_10y is not None and val_2y is not None:
                macro_data["yield_curve_spread"] = val_10y - val_2y
        except Exception as exc:
            warnings.append(f"Treasury yields unavailable: {exc}")

        # M2 money supply
        try:
            m2 = await fred.get_m2_money_supply()
            m2 = m2.dropna()
            if len(m2) >= 13:
                latest = float(m2.iloc[-1])
                prior = float(m2.iloc[-13])
                if prior != 0:
                    macro_data["m2_yoy_growth"] = latest / prior - 1
        except Exception as exc:
            warnings.append(f"M2 unavailable: {exc}")

    except Exception as exc:
        warnings.append(f"FRED provider unavailable: {exc}")

    # VIX from yfinance
    try:
        from data_providers.yfinance_provider import YFinanceProvider

        vix_provider = YFinanceProvider()
        vix_df = await vix_provider.get_price_history(
            "^VIX", period="3mo", interval="1d",
        )
        if vix_df is not None and not vix_df.empty:
            vix_close = vix_df["Close"]
            macro_data["vix_current"] = float(vix_close.iloc[-1])
            if len(vix_close) >= 20:
                macro_data["vix_sma_20"] = float(
                    vix_close.rolling(20).mean().iloc[-1],
                )
    except Exception as exc:
        warnings.append(f"VIX unavailable: {exc}")

    # Run detector
    detector = RegimeDetector()
    result = detector.detect_regime(
        macro_data=macro_data if macro_data else None,
    )

    return {"data": result, "warnings": warnings}


@router.get("/history")
async def regime_history(
    days: int = Query(90, ge=1, le=365),
    db_path: str = Depends(get_db_path),
) -> dict[str, Any]:
    """Return regime detection history with duration information."""
    store = RegimeHistoryStore(db_path)
    data = await store.get_history(days)
    return {"data": data, "warnings": []}
