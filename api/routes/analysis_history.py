"""Analysis history endpoints — browse past analysis results."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from api.deps import get_db_path

import aiosqlite

router = APIRouter()

_COLUMNS = (
    "id, ticker, asset_type, final_signal, final_confidence, "
    "regime, raw_score, consensus_score, "
    "agent_signals_json, reasoning, created_at"
)


@router.get("/history")
async def get_analysis_history(
    ticker: str | None = Query(default=None, description="Filter by ticker"),
    signal: str | None = Query(default=None, description="Filter by final signal"),
    limit: int = Query(default=20, ge=1, le=500, description="Max rows"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db_path: str = Depends(get_db_path),
):
    """Return paginated analysis history with optional ticker/signal filters."""
    async with aiosqlite.connect(db_path) as conn:
        conditions: list[str] = []
        params: list[object] = []

        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if signal:
            conditions.append("final_signal = ?")
            params.append(signal)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        rows = await (
            await conn.execute(
                f"SELECT {_COLUMNS} FROM signal_history "
                f"{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            )
        ).fetchall()

        results = []
        for r in rows:
            agent_signals: list[dict] = []
            try:
                agent_signals = json.loads(r[8]) if r[8] else []
            except (json.JSONDecodeError, TypeError):
                pass

            results.append(
                {
                    "id": r[0],
                    "ticker": r[1],
                    "asset_type": r[2],
                    "final_signal": r[3],
                    "final_confidence": r[4],
                    "regime": r[5],
                    "raw_score": r[6],
                    "consensus_score": r[7],
                    "agent_signals": agent_signals,
                    "reasoning": r[9],
                    "created_at": r[10],
                }
            )

        return {"data": results, "warnings": []}


@router.get("/history/tickers")
async def get_analyzed_tickers(
    db_path: str = Depends(get_db_path),
):
    """Return distinct tickers that appear in signal_history."""
    async with aiosqlite.connect(db_path) as conn:
        rows = await (
            await conn.execute(
                "SELECT DISTINCT ticker FROM signal_history ORDER BY ticker",
            )
        ).fetchall()

        return {"data": [r[0] for r in rows], "warnings": []}
