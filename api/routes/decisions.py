# api/routes/decisions.py
"""Decision Layer endpoints: propose -> approve/reject -> gated paper execute -> audit."""
from __future__ import annotations

import logging
from typing import Literal

import aiosqlite
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.deps import get_db_path, map_ticker, resolve_asset_type
from api.models import (
    ApproveDecisionRequest,
    CreateDecisionRequest,
    ErrorDetail,
    ErrorResponse,
    RejectDecisionRequest,
)
from decisions.audit import verify_chain
from decisions.manager import DecisionManager
from decisions.models import DecisionError
from engine.pipeline import AnalysisPipeline
from execution.adapter import ExecutionAdapter
from execution.paper import PaperExecutionAdapter

logger = logging.getLogger("investment_agent.api.decisions")

router = APIRouter()


def _build_adapter() -> ExecutionAdapter:
    """Seam for tests to inject a stub paper adapter."""
    return PaperExecutionAdapter()


def _error(err: DecisionError) -> JSONResponse:
    return JSONResponse(
        status_code=err.http_status,
        content=ErrorResponse(
            error=ErrorDetail(code=err.code, message=err.message)
        ).model_dump(),
    )


@router.post("")
async def create_decision(
    body: CreateDecisionRequest, db_path: str = Depends(get_db_path)
):
    asset_type = resolve_asset_type(body.ticker, body.asset_type)
    yf_ticker = map_ticker(body.ticker, asset_type)
    pipeline = AnalysisPipeline(db_path=db_path, use_adaptive_weights=False)
    try:
        signal = await pipeline.analyze_ticker(yf_ticker, asset_type, portfolio=None)
    except Exception as exc:  # analysis/data failure
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error=ErrorDetail(code="UPSTREAM_ERROR", message=str(exc))
            ).model_dump(),
        )
    mgr = DecisionManager(db_path)
    proposal = await mgr.create_proposal(signal, quantity=body.quantity)
    return {"data": proposal.to_dict(), "warnings": signal.warnings}


@router.get("")
async def list_decisions(
    status: Literal["pending", "approved", "rejected", "executed", "expired"] | None = Query(None),
    db_path: str = Depends(get_db_path),
):
    mgr = DecisionManager(db_path)
    items = await mgr.list(status=status)
    return {"data": [p.to_summary() for p in items], "warnings": []}


@router.get("/audit/verify")
async def verify_audit_chain(db_path: str = Depends(get_db_path)):
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    try:
        result = await verify_chain(conn)
    finally:
        await conn.close()
    return {"data": result, "warnings": []}


@router.get("/{decision_id}")
async def get_decision(decision_id: int, db_path: str = Depends(get_db_path)):
    mgr = DecisionManager(db_path)
    proposal = await mgr.get(decision_id)
    if proposal is None:
        return _error(DecisionError(
            "DECISION_NOT_FOUND", f"No decision with id {decision_id}", 404
        ))
    return {"data": proposal.to_dict(), "warnings": []}


@router.get("/{decision_id}/audit")
async def get_decision_audit(decision_id: int, db_path: str = Depends(get_db_path)):
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    try:
        rows = await (await conn.execute(
            "SELECT id, decision_id, event_type, actor, payload_json, prev_hash, "
            "entry_hash, created_at FROM decision_audit WHERE decision_id=? ORDER BY id",
            (decision_id,),
        )).fetchall()
    finally:
        await conn.close()
    return {"data": [dict(r) for r in rows], "warnings": []}


@router.post("/{decision_id}/approve")
async def approve_decision(
    decision_id: int, body: ApproveDecisionRequest, db_path: str = Depends(get_db_path)
):
    mgr = DecisionManager(db_path)
    try:
        proposal = await mgr.approve(decision_id, actor=body.actor)
    except DecisionError as err:
        return _error(err)
    return {"data": proposal.to_dict(), "warnings": []}


@router.post("/{decision_id}/reject")
async def reject_decision(
    decision_id: int, body: RejectDecisionRequest, db_path: str = Depends(get_db_path)
):
    mgr = DecisionManager(db_path)
    try:
        proposal = await mgr.reject(decision_id, actor=body.actor, note=body.note)
    except DecisionError as err:
        return _error(err)
    return {"data": proposal.to_dict(), "warnings": []}


@router.post("/{decision_id}/execute")
async def execute_decision(decision_id: int, db_path: str = Depends(get_db_path)):
    mgr = DecisionManager(db_path)
    adapter = _build_adapter()
    try:
        proposal = await mgr.execute(decision_id, adapter)
    except DecisionError as err:
        return _error(err)
    return {"data": proposal.to_dict(), "warnings": []}
