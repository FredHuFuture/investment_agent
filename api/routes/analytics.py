"""API routes for portfolio performance analytics."""
from __future__ import annotations

import json

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db_path
from engine.analytics import VALID_BENCHMARKS, PortfolioAnalytics

router = APIRouter()


@router.get("/value-history")
async def value_history(
    days: int = Query(90, ge=1, le=365),
    db_path: str = Depends(get_db_path),
):
    """Portfolio value over time for charting."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_value_history(days=days)
    return {"data": data, "warnings": []}


@router.get("/performance")
async def performance_summary(db_path: str = Depends(get_db_path)):
    """Overall performance metrics (win rate, avg P&L, etc.)."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_performance_summary()
    return {"data": data, "warnings": []}


@router.get("/monthly-returns")
async def monthly_returns(db_path: str = Depends(get_db_path)):
    """Monthly P&L breakdown."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_monthly_returns()
    return {"data": data, "warnings": []}


@router.get("/top-performers")
async def top_performers(
    limit: int = Query(5, ge=1, le=50),
    db_path: str = Depends(get_db_path),
):
    """Best and worst trades by return percentage."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_top_performers(limit=limit)
    return {"data": data, "warnings": []}


@router.get("/risk")
async def portfolio_risk(
    days: int = Query(90, ge=7, le=365),
    db_path: str = Depends(get_db_path),
):
    """Portfolio risk metrics.

    Returns historical-simulation VaR and CVaR at 95% and 99% confidence
    (SIG-01, SIG-06) computed via QuantStats on the portfolio return series.

    Fields: daily_volatility, annualized_volatility, sharpe_ratio, sortino_ratio,
    max_drawdown_pct, current_drawdown_pct, var_95, var_99, cvar_95, cvar_99,
    portfolio_var, portfolio_var_method, best_day_pct, worst_day_pct,
    positive_days, negative_days, data_points.

    When portfolio_snapshots < 10 rows in the window, var/cvar fields are null
    and portfolio_var_method == "insufficient_data".
    """
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_portfolio_risk(days=days)
    return {"data": data, "warnings": []}


@router.get("/benchmark")
async def benchmark_comparison(
    days: int = Query(90, ge=7, le=365),
    benchmark: str = Query("SPY"),
    db_path: str = Depends(get_db_path),
):
    """Compare portfolio performance against a benchmark (e.g., SPY).

    UI-02 SSRF mitigation (Threat T-04-03): ``benchmark`` must be in
    ``VALID_BENCHMARKS`` allowlist. Free-form tickers are rejected with
    HTTP 400 before the value reaches the yfinance provider.
    """
    from data_providers.factory import get_provider

    ticker = benchmark.upper().strip()
    if ticker not in VALID_BENCHMARKS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown benchmark: {ticker}. "
                f"Allowed: {', '.join(sorted(VALID_BENCHMARKS))}"
            ),
        )

    analytics = PortfolioAnalytics(db_path)
    provider = get_provider()
    data = await analytics.get_benchmark_comparison(
        provider=provider,
        benchmark_ticker=ticker,
        days=days,
    )
    return {"data": data, "warnings": []}


@router.get("/returns")
async def returns_ttwror_irr(
    days: int = Query(365, ge=7, le=1825),
    db_path: str = Depends(get_db_path),
):
    """UI-01: TTWROR + IRR aggregate and per-position breakdown.

    Returns {data: {aggregate: {ttwror, irr, snapshot_count, ...},
                    positions: [{ticker, ttwror, irr, hold_days, ...}]},
             warnings: []}.

    When fewer than 2 portfolio_snapshots exist in the window, aggregate
    fields are null and the frontend should display "--".
    """
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_ttwror_irr(days=days)
    return {"data": data, "warnings": []}


@router.get("/daily-pnl")
async def daily_pnl(
    days: int = Query(365, ge=7, le=1825),
    db_path: str = Depends(get_db_path),
):
    """UI-05: daily P&L series for TradeNote-style calendar heatmap.

    Returns {data: [{date: "YYYY-MM-DD", pnl: float}], warnings: []}.
    Uses last-of-day snapshot semantics (daily close value).
    Empty list when fewer than 2 distinct calendar days exist in the window.
    """
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_daily_pnl_heatmap(days=days)
    return {"data": data, "warnings": []}


@router.get("/cumulative-pnl")
async def cumulative_pnl(db_path: str = Depends(get_db_path)):
    """Cumulative realized P&L curve across all closed trades."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_cumulative_pnl()
    return {"data": data, "warnings": []}


@router.get("/position-pnl/{ticker}")
async def position_pnl_history(
    ticker: str,
    db_path: str = Depends(get_db_path),
):
    """P&L history timeline for a specific position."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_position_pnl_history(ticker)
    if not data:
        return {"data": [], "warnings": [f"No data found for {ticker.upper()}"]}
    return {"data": data, "warnings": []}


@router.get("/correlations")
async def portfolio_correlations(
    lookback_days: int = Query(90, ge=30, le=365),
    db_path: str = Depends(get_db_path),
):
    """Pairwise correlation matrix for portfolio holdings."""
    from engine.correlation import calculate_portfolio_correlations
    from data_providers.factory import get_provider

    # Get active tickers from DB
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        rows = await (
            await conn.execute(
                "SELECT DISTINCT ticker FROM active_positions WHERE status = 'active'"
            )
        ).fetchall()

    tickers = [row["ticker"] for row in rows]
    if len(tickers) < 2:
        return {
            "data": {
                "correlation_matrix": {},
                "avg_correlation": 0.0,
                "high_correlation_pairs": [],
                "concentration_risk": "LOW",
                "tickers": tickers,
                "warnings": ["Need at least 2 positions for correlation analysis."],
            },
            "warnings": [],
        }

    provider = get_provider()
    result = await calculate_portfolio_correlations(tickers, provider, lookback_days)

    # Convert tuple keys to string keys for JSON serialization
    matrix = {}
    for key, val in result.get("correlation_matrix", {}).items():
        if isinstance(key, tuple):
            matrix[f"{key[0]}:{key[1]}"] = val
        else:
            matrix[str(key)] = val
    result["correlation_matrix"] = matrix

    # Convert tuple high_correlation_pairs to lists for JSON
    result["high_correlation_pairs"] = [
        list(pair) for pair in result.get("high_correlation_pairs", [])
    ]

    result["tickers"] = tickers

    return {"data": result, "warnings": result.pop("warnings", [])}


@router.get("/daily-return")
async def daily_return(db_path: str = Depends(get_db_path)):
    """Daily portfolio return (latest vs previous snapshot)."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        rows = await (
            await conn.execute(
                "SELECT date, total_value FROM value_snapshots "
                "ORDER BY date DESC LIMIT 2"
            )
        ).fetchall()

    if len(rows) < 2:
        return {
            "data": {
                "return_pct": 0.0,
                "return_dollars": 0.0,
                "date": rows[0]["date"] if rows else "",
                "previous_value": 0.0,
                "current_value": rows[0]["total_value"] if rows else 0.0,
            },
            "warnings": ["Insufficient snapshots to compute daily return."],
        }

    current = rows[0]
    previous = rows[1]
    dollar_change = current["total_value"] - previous["total_value"]
    pct_change = (
        (dollar_change / previous["total_value"]) * 100
        if previous["total_value"]
        else 0.0
    )

    return {
        "data": {
            "return_pct": round(pct_change, 4),
            "return_dollars": round(dollar_change, 2),
            "date": current["date"],
            "previous_value": previous["total_value"],
            "current_value": current["total_value"],
        },
        "warnings": [],
    }


@router.get("/drawdown-series")
async def drawdown_series(
    days: int = Query(90, ge=1, le=365),
    db_path: str = Depends(get_db_path),
):
    """Drawdown percentage series from portfolio value snapshots."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_drawdown_series(days=days)
    return {"data": data, "warnings": []}


@router.get("/rolling-sharpe")
async def rolling_sharpe(
    days: int = Query(90, ge=1, le=365),
    window: int = Query(30, ge=5, le=120),
    db_path: str = Depends(get_db_path),
):
    """Rolling Sharpe ratio over a sliding window."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_rolling_sharpe(days=days, window=window)
    return {"data": data, "warnings": []}


@router.get("/monthly-heatmap")
async def monthly_heatmap(db_path: str = Depends(get_db_path)):
    """Year/month return grid for heatmap display."""
    analytics = PortfolioAnalytics(db_path)
    data = await analytics.get_monthly_heatmap()
    return {"data": data, "warnings": []}


@router.get("/attribution")
async def performance_attribution(db_path: str = Depends(get_db_path)):
    """Per-position P&L attribution with contribution percentages."""
    import asyncio
    from api.deps import map_ticker
    from data_providers.factory import get_provider

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        rows = await (
            await conn.execute(
                "SELECT ticker, asset_type, sector, quantity, avg_cost, "
                "status, realized_pnl "
                "FROM active_positions"
            )
        ).fetchall()

    if not rows:
        return {"data": [], "warnings": []}

    # Separate open and closed positions
    open_positions = [r for r in rows if r["status"] != "closed"]
    closed_positions = [r for r in rows if r["status"] == "closed"]

    # Fetch live prices for open positions
    price_map: dict[str, float] = {}
    warnings: list[str] = []

    async def _fetch(ticker: str, asset_type: str) -> tuple[str, float]:
        try:
            provider = get_provider(asset_type)
            yf_ticker = map_ticker(ticker, asset_type)
            price = await provider.get_current_price(yf_ticker)
            return ticker, price
        except Exception:
            return ticker, 0.0

    if open_positions:
        results = await asyncio.gather(
            *[_fetch(r["ticker"], r["asset_type"]) for r in open_positions]
        )
        price_map = dict(results)

    entries: list[dict] = []
    for row in rows:
        ticker = row["ticker"]
        avg_cost = row["avg_cost"]
        quantity = row["quantity"]
        sector = row["sector"]
        status = row["status"]

        if status == "closed":
            pnl = row["realized_pnl"] or 0.0
            cost_basis = avg_cost * quantity
            pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0
        else:
            current_price = price_map.get(ticker, 0.0)
            if current_price <= 0:
                warnings.append(f"Could not fetch price for {ticker}")
                continue
            pnl = (current_price - avg_cost) * quantity
            pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0

        entries.append({
            "ticker": ticker,
            "sector": sector,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "contribution_pct": 0.0,  # computed below
            "status": status,
        })

    # Compute contribution percentages
    total_abs_pnl = sum(abs(e["pnl"]) for e in entries)
    if total_abs_pnl > 0:
        for e in entries:
            e["contribution_pct"] = round(e["pnl"] / total_abs_pnl * 100, 2)

    # Sort by absolute contribution descending
    entries.sort(key=lambda e: abs(e["contribution_pct"]), reverse=True)

    return {"data": entries, "warnings": warnings}


@router.get("/activity-feed")
async def activity_feed(
    limit: int = Query(20, ge=1, le=100),
    db_path: str = Depends(get_db_path),
):
    """Unified activity feed aggregating daemon runs, alerts, and signals."""
    entries: list[dict] = []

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # 1. Daemon runs
        try:
            rows = await (
                await conn.execute(
                    "SELECT job_name, status, started_at, duration_ms, error_message "
                    "FROM daemon_runs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                )
            ).fetchall()
            for row in rows:
                status = row["status"] or "unknown"
                severity = "critical" if status in ("error", "failed") else "info"
                if row["error_message"]:
                    detail = row["error_message"]
                elif row["duration_ms"] is not None:
                    detail = f"Completed in {row['duration_ms']}ms"
                else:
                    detail = None
                entries.append(
                    {
                        "type": "daemon_run",
                        "timestamp": row["started_at"],
                        "title": f"{row['job_name']} \u2014 {status}",
                        "detail": detail,
                        "severity": severity,
                        "icon": "cog",
                    }
                )
        except Exception:
            pass  # table may not exist yet

        # 2. Monitoring alerts
        try:
            rows = await (
                await conn.execute(
                    "SELECT ticker, alert_type, severity, message, created_at "
                    "FROM monitoring_alerts ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            ).fetchall()
            for row in rows:
                entries.append(
                    {
                        "type": "alert",
                        "timestamp": row["created_at"],
                        "title": f"{row['alert_type']} \u2014 {row['ticker'] or 'System'}",
                        "detail": row["message"],
                        "severity": row["severity"],
                        "icon": "bell",
                    }
                )
        except Exception:
            pass

        # 3. Signal history
        try:
            rows = await (
                await conn.execute(
                    "SELECT ticker, final_signal, final_confidence, created_at "
                    "FROM signal_history ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            ).fetchall()
            for row in rows:
                confidence_pct = (
                    round(row["final_confidence"] * 100)
                    if row["final_confidence"] is not None
                    else 0
                )
                entries.append(
                    {
                        "type": "signal",
                        "timestamp": row["created_at"],
                        "title": f"{row['ticker']} \u2192 {row['final_signal']}",
                        "detail": f"Confidence: {confidence_pct}%",
                        "severity": "info",
                        "icon": "chart",
                    }
                )
        except Exception:
            pass

    # Merge and sort by timestamp descending, take top `limit`
    entries.sort(key=lambda e: e["timestamp"] or "", reverse=True)
    return {"data": entries[:limit], "warnings": []}


@router.get("/snapshot-compare")
async def snapshot_compare(
    date_a: str = Query(..., description="Start date YYYY-MM-DD"),
    date_b: str = Query(..., description="End date YYYY-MM-DD"),
    db_path: str = Depends(get_db_path),
):
    """Compare two portfolio snapshots by date."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Find closest snapshot on or before each date
        row_a = await (
            await conn.execute(
                "SELECT total_value, cash, positions_json, timestamp "
                "FROM portfolio_snapshots "
                "WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1",
                (date_a + "T23:59:59",),
            )
        ).fetchone()

        row_b = await (
            await conn.execute(
                "SELECT total_value, cash, positions_json, timestamp "
                "FROM portfolio_snapshots "
                "WHERE timestamp <= ? ORDER BY timestamp DESC LIMIT 1",
                (date_b + "T23:59:59",),
            )
        ).fetchone()

    if not row_a or not row_b:
        raise HTTPException(
            status_code=404,
            detail="No snapshot found for one or both dates.",
        )

    total_a = row_a["total_value"]
    total_b = row_b["total_value"]
    value_change = total_b - total_a
    value_change_pct = (value_change / total_a * 100) if total_a else 0.0

    # Parse positions
    positions_a_raw = json.loads(row_a["positions_json"] or "[]")
    positions_b_raw = json.loads(row_b["positions_json"] or "[]")

    def _build_map(positions: list) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for p in positions:
            ticker = p.get("ticker", "")
            if ticker:
                result[ticker] = p
        return result

    map_a = _build_map(positions_a_raw)
    map_b = _build_map(positions_b_raw)

    tickers_a = set(map_a.keys())
    tickers_b = set(map_b.keys())

    positions_added = sorted(tickers_b - tickers_a)
    positions_removed = sorted(tickers_a - tickers_b)

    positions_changed: list[dict] = []
    for ticker in sorted(tickers_a & tickers_b):
        pa = map_a[ticker]
        pb = map_b[ticker]
        val_a = pa.get("market_value", pa.get("quantity", 0) * pa.get("avg_cost", 0))
        val_b = pb.get("market_value", pb.get("quantity", 0) * pb.get("avg_cost", 0))
        chg_pct = ((val_b - val_a) / val_a * 100) if val_a else 0.0
        positions_changed.append({
            "ticker": ticker,
            "value_a": round(val_a, 2),
            "value_b": round(val_b, 2),
            "change_pct": round(chg_pct, 2),
        })

    return {
        "data": {
            "date_a": date_a,
            "date_b": date_b,
            "total_value_a": round(total_a, 2),
            "total_value_b": round(total_b, 2),
            "value_change": round(value_change, 2),
            "value_change_pct": round(value_change_pct, 2),
            "positions_added": positions_added,
            "positions_removed": positions_removed,
            "positions_changed": positions_changed,
        },
        "warnings": [],
    }


@router.get("/sector-performance")
async def sector_performance(db_path: str = Depends(get_db_path)):
    """Aggregate P&L by sector from both open and closed positions."""
    import asyncio
    from api.deps import map_ticker
    from data_providers.factory import get_provider

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        rows = await (
            await conn.execute(
                "SELECT ticker, asset_type, sector, quantity, avg_cost, "
                "status, realized_pnl "
                "FROM active_positions"
            )
        ).fetchall()

    if not rows:
        return {"data": [], "warnings": []}

    open_positions = [r for r in rows if r["status"] != "closed"]
    closed_positions = [r for r in rows if r["status"] == "closed"]

    # Fetch live prices for open positions
    price_map: dict[str, float] = {}
    warnings: list[str] = []

    async def _fetch(ticker: str, asset_type: str) -> tuple[str, float]:
        try:
            provider = get_provider(asset_type)
            yf_ticker = map_ticker(ticker, asset_type)
            price = await provider.get_current_price(yf_ticker)
            return ticker, price
        except Exception:
            return ticker, 0.0

    if open_positions:
        results = await asyncio.gather(
            *[_fetch(r["ticker"], r["asset_type"]) for r in open_positions]
        )
        price_map = dict(results)

    # Build per-sector aggregation
    sectors: dict[str, dict] = {}

    for row in rows:
        ticker = row["ticker"]
        sector = row["sector"] or "Unknown"
        avg_cost = row["avg_cost"]
        quantity = row["quantity"]
        status = row["status"]
        cost_basis = avg_cost * quantity

        if status == "closed":
            pnl = row["realized_pnl"] or 0.0
            pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0
        else:
            current_price = price_map.get(ticker, 0.0)
            if current_price <= 0:
                warnings.append(f"Could not fetch price for {ticker}")
                continue
            pnl = (current_price - avg_cost) * quantity
            pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0

        if sector not in sectors:
            sectors[sector] = {
                "sector": sector,
                "total_pnl": 0.0,
                "total_cost_basis": 0.0,
                "position_count": 0,
                "best_ticker": None,
                "best_pnl_pct": float("-inf"),
                "worst_ticker": None,
                "worst_pnl_pct": float("inf"),
            }

        s = sectors[sector]
        s["total_pnl"] += pnl
        s["total_cost_basis"] += cost_basis
        s["position_count"] += 1

        if pnl_pct > s["best_pnl_pct"]:
            s["best_pnl_pct"] = pnl_pct
            s["best_ticker"] = ticker
        if pnl_pct < s["worst_pnl_pct"]:
            s["worst_pnl_pct"] = pnl_pct
            s["worst_ticker"] = ticker

    # Build result list
    result = []
    for s in sectors.values():
        total_pnl_pct = (
            (s["total_pnl"] / s["total_cost_basis"] * 100)
            if s["total_cost_basis"]
            else 0.0
        )
        result.append({
            "sector": s["sector"],
            "total_pnl": round(s["total_pnl"], 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "position_count": s["position_count"],
            "best_ticker": s["best_ticker"],
            "worst_ticker": s["worst_ticker"],
        })

    # Sort by total_pnl descending
    result.sort(key=lambda x: x["total_pnl"], reverse=True)

    return {"data": result, "warnings": warnings}
