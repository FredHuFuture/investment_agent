"""Adaptive weights endpoint (LIVE-03 — Phase 6).

Rewrites the legacy /weights endpoint to return per-(agent, asset_type) state
from the new `agent_weights` table, exposes IC-IR-suggested weights side-by-side,
and adds apply + override mutations. Consumes existing compute_ic_weights from
Phase 2 SIG-03 — does not reimplement IC-IR math.

Legacy contract is intentionally superseded: the old donut WeightsPage.tsx
consumes the OLD shape and will need the Phase 6 frontend plan (06-02) to
land before the UI is usable again. See SUMMARY.md for details.

Pipeline wiring to load_weights_from_db is DEFERRED to Phase 7 AN-02 drift
detector. This plan only lands the helper + endpoints; pipeline.py and daemon
call sites remain on DEFAULT_WEIGHTS until then.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_db_path
from api.models import (
    ApplyIcIrResponse,
    OverrideRequest,
    OverrideResponse,
    WeightsOverviewResponse,
)
from engine.aggregator import SignalAggregator

_logger = logging.getLogger(__name__)
router = APIRouter()

# Known agent set — mirrors api/routes/calibration.py::KNOWN_AGENTS.
# PATCH override rejects anything not in this set to prevent DDL-level pollution
# (T-06-01-01 mitigation).
KNOWN_AGENTS = {
    "TechnicalAgent",
    "FundamentalAgent",
    "MacroAgent",
    "SentimentAgent",
    "CryptoAgent",
    "SummaryAgent",
}
VALID_ASSET_TYPES = {"stock", "btc", "eth"}


async def _read_current_weights(
    conn: aiosqlite.Connection,
) -> tuple[
    dict[str, dict[str, float]],
    dict[str, dict[str, dict[str, bool]]],
    str,
    str,
]:
    """Return (current_weights, overrides, dominant_source, latest_updated_at).

    current_weights: asset_type -> {agent: weight}, EXCLUDES excluded=1 rows,
                     renormalized so each asset_type sums to 1.0 (FOUND-05).
    overrides:       asset_type -> {agent: {excluded, manual_override}} only
                     for rows where manual_override=1 OR excluded=1.
    dominant_source: 'manual' if any row is 'manual', else 'ic_ir' if any row
                     is 'ic_ir', else 'default'.
    """
    conn.row_factory = aiosqlite.Row
    rows = await (
        await conn.execute(
            "SELECT agent_name, asset_type, weight, manual_override, "
            "excluded, source, updated_at FROM agent_weights"
        )
    ).fetchall()

    raw: dict[str, dict[str, float]] = {}
    overrides: dict[str, dict[str, dict[str, bool]]] = {
        at: {} for at in VALID_ASSET_TYPES
    }
    sources: set[str] = set()
    latest_updated_at = ""

    for r in rows:
        at = r["asset_type"]
        sources.add(r["source"])
        if r["updated_at"] > latest_updated_at:
            latest_updated_at = r["updated_at"]
        if int(r["manual_override"]) == 1 or int(r["excluded"]) == 1:
            overrides.setdefault(at, {})[r["agent_name"]] = {
                "excluded": bool(r["excluded"]),
                "manual_override": bool(r["manual_override"]),
            }
        if int(r["excluded"]) == 1:
            continue
        raw.setdefault(at, {})[r["agent_name"]] = float(r["weight"])

    # Renormalize each asset_type to sum 1.0 (FOUND-05 contract).
    current: dict[str, dict[str, float]] = {}
    for at, agents in raw.items():
        total = sum(agents.values())
        if total > 0:
            current[at] = {k: round(v / total, 4) for k, v in agents.items()}
        else:
            current[at] = agents

    # Dominant source: manual > ic_ir > default
    if "manual" in sources:
        source = "manual"
    elif "ic_ir" in sources:
        source = "ic_ir"
    else:
        source = "default"

    return current, overrides, source, latest_updated_at


async def _compute_suggested_ic_ir(
    db_path: str,
) -> tuple[dict[str, dict[str, float] | None], int]:
    """Compute IC-IR-suggested weights via existing WeightAdapter.compute_ic_weights.

    Returns ({asset_type: weights_or_None}, total_sample_size).
    If compute_ic_weights returns None (corpus empty), all per-asset-type values are None.

    Deferred imports prevent circular import between api.routes.weights,
    engine.weight_adapter, and engine.aggregator (design_decision 5).
    """
    from engine.weight_adapter import WeightAdapter  # deferred
    from tracking.store import SignalStore
    from tracking.tracker import SignalTracker

    store = SignalStore(db_path)
    tracker = SignalTracker(store)
    adapter = WeightAdapter(db_path=db_path)
    adaptive = await adapter.compute_ic_weights(
        tracker=tracker,
        asset_types=["stock", "btc", "eth"],
    )
    if adaptive is None:
        return ({at: None for at in VALID_ASSET_TYPES}, 0)
    suggested: dict[str, dict[str, float] | None] = {}
    for at in VALID_ASSET_TYPES:
        suggested[at] = adaptive.weights.get(at) or None
    return (suggested, adaptive.sample_size)


@router.get("/weights")
async def get_weights(db_path: str = Depends(get_db_path)):
    """LIVE-03: Return current per-(agent, asset_type) weights, IC-IR suggestions, overrides.

    Supersedes the legacy /weights response shape. The old donut WeightsPage.tsx
    will break visually until plan 06-02 ships the new frontend.
    """
    async with aiosqlite.connect(db_path) as conn:
        current, overrides, source, updated_at = await _read_current_weights(conn)
    suggested, sample_size = await _compute_suggested_ic_ir(db_path)

    warnings: list[str] = []
    if all(v is None for v in suggested.values()):
        warnings.append(
            "IC-IR suggestions unavailable: backtest_signal_history corpus "
            "has insufficient data. Run POST /analytics/calibration/rebuild-corpus."
        )

    return {
        "data": {
            "current": current,
            "suggested_ic_ir": suggested,
            "overrides": overrides,
            "source": source,
            "computed_at": updated_at or datetime.now(timezone.utc).isoformat(),
            "sample_size": sample_size,
        },
        "warnings": warnings,
    }


@router.post("/weights/apply-ic-ir", response_model=ApplyIcIrResponse)
async def apply_ic_ir_weights(db_path: str = Depends(get_db_path)):
    """LIVE-03: Persist IC-IR-suggested weights to agent_weights with source='ic_ir'.

    Returns 409 NO_IC_IR_DATA when corpus is empty.

    T-06-01-04 mitigation: ON CONFLICT ... WHERE agent_weights.manual_override=0
    preserves rows where the user explicitly set manual_override=1.
    """
    suggested, sample_size = await _compute_suggested_ic_ir(db_path)
    if all(v is None for v in suggested.values()):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NO_IC_IR_DATA",
                "message": (
                    "IC-IR weights unavailable — backtest_signal_history is "
                    "empty or has insufficient rows. Populate the corpus first "
                    "via POST /analytics/calibration/rebuild-corpus."
                ),
            },
        )

    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        # UPSERT each asset_type's agents with source='ic_ir'.
        # WHERE agent_weights.manual_override=0 preserves user overrides
        # (T-06-01-04 mitigated).
        for at, agent_map in suggested.items():
            if agent_map is None:
                continue
            for agent_name, weight in agent_map.items():
                await conn.execute(
                    """
                    INSERT INTO agent_weights
                        (agent_name, asset_type, weight, manual_override,
                         excluded, source, updated_at)
                    VALUES (?, ?, ?, 0, 0, 'ic_ir', ?)
                    ON CONFLICT (agent_name, asset_type) DO UPDATE SET
                        weight = excluded.weight,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    WHERE agent_weights.manual_override = 0
                    """,
                    (agent_name, at, float(weight), now),
                )
        await conn.commit()
        current, _, source, _ = await _read_current_weights(conn)

    return ApplyIcIrResponse(
        applied=True,
        weights=current,
        source=source,
        sample_size=sample_size,
    )


@router.patch("/weights/override", response_model=OverrideResponse)
async def override_agent_weight(
    body: OverrideRequest,
    db_path: str = Depends(get_db_path),
):
    """LIVE-03: Toggle an agent's excluded flag (persists manual_override=1).

    T-06-01-01 mitigation: unknown agents rejected via KNOWN_AGENTS allowlist.
    T-06-01-02 mitigation: asset_type validated by Pydantic pattern + DB CHECK.
    T-06-01-03 mitigation: UPSERT ON CONFLICT serializes concurrent writes safely.
    """
    if body.agent not in KNOWN_AGENTS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UNKNOWN_AGENT",
                "message": (
                    f"Unknown agent: {body.agent!r}. "
                    f"Known agents: {sorted(KNOWN_AGENTS)}"
                ),
            },
        )
    # body.asset_type already validated by Pydantic pattern="^(stock|btc|eth)$"

    now = datetime.now(timezone.utc).isoformat()
    excluded_int = 1 if body.excluded else 0

    async with aiosqlite.connect(db_path) as conn:
        # UPSERT: if row missing (agent added post-seed), insert with weight=0.0.
        # ON CONFLICT updates excluded, manual_override, source, updated_at.
        await conn.execute(
            """
            INSERT INTO agent_weights
                (agent_name, asset_type, weight, manual_override,
                 excluded, source, updated_at)
            VALUES (?, ?, 0.0, 1, ?, 'manual', ?)
            ON CONFLICT (agent_name, asset_type) DO UPDATE SET
                manual_override = 1,
                excluded = excluded.excluded,
                source = 'manual',
                updated_at = excluded.updated_at
            """,
            (body.agent, body.asset_type, excluded_int, now),
        )
        await conn.commit()
        current, _, _, _ = await _read_current_weights(conn)

    return OverrideResponse(
        agent=body.agent,
        asset_type=body.asset_type,
        excluded=body.excluded,
        manual_override=True,
        renormalized_weights=current.get(body.asset_type, {}),
        source="manual",
    )
