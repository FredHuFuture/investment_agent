"""API routes for data export (CSV / JSON)."""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from api.deps import get_db_path
from export.portfolio_report import PortfolioExporter

router = APIRouter()


@router.get("/portfolio/csv")
async def export_portfolio_csv(db_path: str = Depends(get_db_path)):
    """Download current portfolio as CSV."""
    exporter = PortfolioExporter(db_path)
    result = await exporter.export_portfolio_csv()
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=result.content_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )


@router.get("/trades/csv")
async def export_trades_csv(db_path: str = Depends(get_db_path)):
    """Download trade journal (closed positions) as CSV."""
    exporter = PortfolioExporter(db_path)
    result = await exporter.export_closed_positions_csv()
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=result.content_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )


@router.get("/portfolio/report")
async def export_portfolio_report(db_path: str = Depends(get_db_path)):
    """Download comprehensive portfolio report as JSON."""
    exporter = PortfolioExporter(db_path)
    result = await exporter.export_portfolio_report_json()
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=result.content_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )


@router.get("/signals/csv")
async def export_signals_csv(
    ticker: str | None = Query(None),
    limit: int = Query(100),
    db_path: str = Depends(get_db_path),
):
    """Download signal history as CSV."""
    exporter = PortfolioExporter(db_path)
    result = await exporter.export_signals_csv(ticker=ticker, limit=limit)
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=result.content_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )


@router.get("/alerts/csv")
async def export_alerts_csv(
    limit: int = Query(100),
    db_path: str = Depends(get_db_path),
):
    """Download alert history as CSV."""
    exporter = PortfolioExporter(db_path)
    result = await exporter.export_alerts_csv(limit=limit)
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=result.content_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )


@router.get("/performance/csv")
async def export_performance_csv(db_path: str = Depends(get_db_path)):
    """Download performance summary and monthly returns as CSV."""
    exporter = PortfolioExporter(db_path)
    result = await exporter.export_performance_csv()
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=result.content_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )


@router.get("/risk/csv")
async def export_risk_csv(
    days: int = Query(90, ge=7, le=365),
    db_path: str = Depends(get_db_path),
):
    """Download risk metrics snapshot as CSV."""
    exporter = PortfolioExporter(db_path)
    result = await exporter.export_risk_csv(days=days)
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=result.content_type,
        headers={"Content-Disposition": f"attachment; filename={result.filename}"},
    )
