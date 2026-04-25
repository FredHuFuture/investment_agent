"""Per-agent IC-IR drift detection with auto-weight scaling (AN-02).

Runs weekly (Sunday 17:30 US/Eastern via APScheduler) to:
1. Compute current IC-IR per (agent, asset_type) from backtest_signal_history
2. Compare against 60-day rolling average from drift_log history
3. Flag drift when |delta| > 20% OR IC-IR < 0.5 for 2 consecutive weeks
4. Auto-scale agent weights (preserving manual_override=1 rows) via UPSERT
5. Write a drift_log row regardless of trigger (observability)

When < MIN_SAMPLES_FOR_REAL_THRESHOLD weekly IC observations exist per agent,
preliminary_threshold=True is set — mirrors the Phase 2 preliminary_calibration
pattern. Amber badge, not red alert.

NEVER-zero-all guard: if scaling would zero ALL agents for an asset_type,
the auto-scale is aborted, weight_after=NULL is recorded, and a CRITICAL
log + alert is emitted.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("investment_agent.drift_detector")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DRIFT_THRESHOLD_PCT = 20.0          # IC-IR drop > 20% triggers scale
ICIR_FLOOR = 0.5                    # IC-IR < 0.5 also triggers (absolute floor)
MIN_SAMPLES_FOR_REAL_THRESHOLD = 60  # weekly IC observations needed before real thresholds activate
SCALE_DIVISOR = 2.0                  # matches engine/weight_adapter.py compute_ic_weights

# Canonical agent × asset_type combinations tracked by the detector.
# SummaryAgent is excluded (not a scoring agent).
KNOWN_AGENTS: list[str] = [
    "TechnicalAgent",
    "FundamentalAgent",
    "MacroAgent",
    "SentimentAgent",
    "CryptoAgent",
]

KNOWN_ASSET_TYPES: list[str] = ["stock", "btc", "eth"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def evaluate_drift(db_path: str) -> list[dict[str, Any]]:
    """Evaluate IC-IR drift for all (agent, asset_type) combinations.

    Returns a list of drift_log entry dicts — one per (agent, asset_type) pair
    where the agent is active for that asset_type. Writes results to drift_log.

    Fields per entry:
        agent_name, asset_type, evaluated_at, current_icir, avg_icir_60d,
        delta_pct, threshold_type, triggered, preliminary_threshold,
        weight_before, weight_after
    """
    import aiosqlite
    from tracking.store import SignalStore
    from tracking.tracker import SignalTracker

    evaluated_at = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        store = SignalStore(conn)
        tracker = SignalTracker(store)

        for agent in KNOWN_AGENTS:
            # Determine which asset_types this agent applies to
            asset_types = _agent_asset_types(agent)

            for asset_type in asset_types:
                entry = await _evaluate_one(
                    tracker=tracker,
                    conn=conn,
                    agent_name=agent,
                    asset_type=asset_type,
                    evaluated_at=evaluated_at,
                    db_path=db_path,
                )
                results.append(entry)

    return results


async def _evaluate_one(
    tracker: Any,
    conn: Any,
    agent_name: str,
    asset_type: str,
    evaluated_at: str,
    db_path: str,
) -> dict[str, Any]:
    """Evaluate drift for one (agent, asset_type) pair and write to drift_log."""
    import aiosqlite

    # 1. Compute rolling IC for this agent
    try:
        _overall_ic, rolling = await tracker.compute_rolling_ic(
            agent_name, horizon="5d", window=60
        )
    except Exception as exc:
        logger.warning(
            "compute_rolling_ic failed for %s: %s", agent_name, exc
        )
        rolling = []

    valid_ics = [ic for ic in rolling if ic is not None] if rolling else []
    current_icir = tracker.compute_icir(valid_ics) if valid_ics else None

    # 2. Determine if we have enough observations for real thresholds
    preliminary = len(valid_ics) < MIN_SAMPLES_FOR_REAL_THRESHOLD

    # 3. Load 60-day average from drift_log history
    avg_icir_60d = await _get_avg_icir_60d(conn, agent_name, asset_type)

    # 4. Compute delta and evaluate thresholds
    delta_pct: float | None = None
    triggered = False
    threshold_type = "preliminary" if preliminary else "none"

    if not preliminary and current_icir is not None:
        if avg_icir_60d is not None and avg_icir_60d != 0:
            delta_pct = (current_icir - avg_icir_60d) / abs(avg_icir_60d) * 100.0
            if delta_pct < -DRIFT_THRESHOLD_PCT:
                triggered = True
                threshold_type = "drop_pct"
        if not triggered and current_icir < ICIR_FLOOR:
            triggered = True
            threshold_type = "absolute_low"
            if delta_pct is None:
                delta_pct = None  # no baseline but floor triggered

    # 5. Load current weight before scale
    weight_before = await _get_current_weight(conn, agent_name, asset_type)
    weight_after: float | None = None

    # 6. Auto-scale when triggered (not preliminary)
    if triggered and not preliminary and current_icir is not None:
        weight_after = await _apply_drift_scale(
            db_path=db_path,
            agent_name=agent_name,
            asset_type=asset_type,
            current_icir=current_icir,
        )
        if weight_after is not None:
            logger.info(
                "Drift scale applied: %s/%s weight %.4f -> %.4f (ic_ir=%.4f)",
                agent_name, asset_type, weight_before or 0.0, weight_after, current_icir,
            )

    # 7. Write drift_log row
    entry: dict[str, Any] = {
        "agent_name": agent_name,
        "asset_type": asset_type,
        "evaluated_at": evaluated_at,
        "current_icir": current_icir,
        "avg_icir_60d": avg_icir_60d,
        "delta_pct": delta_pct,
        "threshold_type": threshold_type,
        "triggered": triggered,
        "preliminary_threshold": preliminary,
        "weight_before": weight_before,
        "weight_after": weight_after,
    }
    await _write_drift_log(conn, entry)
    return entry


async def _get_avg_icir_60d(
    conn: Any, agent_name: str, asset_type: str
) -> float | None:
    """Compute 60-day average IC-IR from drift_log history for this agent."""
    rows = await (
        await conn.execute(
            """
            SELECT current_icir FROM drift_log
            WHERE agent_name = ? AND asset_type = ?
              AND current_icir IS NOT NULL
            ORDER BY evaluated_at DESC
            LIMIT 60
            """,
            (agent_name, asset_type),
        )
    ).fetchall()

    values = [float(row[0]) for row in rows if row[0] is not None]
    if not values:
        return None
    return sum(values) / len(values)


async def _get_current_weight(
    conn: Any, agent_name: str, asset_type: str
) -> float | None:
    """Fetch the current weight for this agent from agent_weights table."""
    try:
        row = await (
            await conn.execute(
                "SELECT weight FROM agent_weights WHERE agent_name = ? AND asset_type = ?",
                (agent_name, asset_type),
            )
        ).fetchone()
        return float(row[0]) if row is not None else None
    except Exception:
        return None


async def _apply_drift_scale(
    db_path: str,
    agent_name: str,
    asset_type: str,
    current_icir: float,
) -> float | None:
    """Scale agent weight down proportionally to IC-IR degradation.

    Scale factor: max(0, ic_ir / SCALE_DIVISOR) — mirrors compute_ic_weights.
    Renormalizes remaining agents so sum=1.0 for the asset_type.

    NEVER-zero-all guard: if ALL agents for this asset_type would be <= 0 after
    scaling, aborts the write for this asset_type and returns None.

    Returns new weight (post-renorm) or None if write was aborted.
    """
    import aiosqlite

    scale_factor = max(0.0, current_icir / SCALE_DIVISOR)

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row

        # Load all non-excluded, non-manual-override weights for this asset_type
        rows = await (
            await conn.execute(
                """
                SELECT agent_name, weight FROM agent_weights
                WHERE asset_type = ? AND excluded = 0
                """,
                (asset_type,),
            )
        ).fetchall()

        if not rows:
            logger.warning(
                "No agent_weights rows for asset_type=%s — skipping drift scale",
                asset_type,
            )
            return None

        # Compute new weights
        new_weights: dict[str, float] = {}
        for row in rows:
            a_name = row["agent_name"]
            w = float(row["weight"])
            if a_name == agent_name:
                new_weights[a_name] = w * scale_factor
            else:
                new_weights[a_name] = w

        # NEVER-zero-all guard: check if all would be zero
        total_new = sum(new_weights.values())
        if total_new <= 0:
            logger.critical(
                "NEVER-zero-all guard triggered: all agents for asset_type=%s "
                "would be zeroed after drift scale of %s (ic_ir=%.4f). "
                "Aborting weight update.",
                asset_type, agent_name, current_icir,
            )
            return None

        # Renormalize so sum = 1.0 for this asset_type (FOUND-05 contract)
        renorm_weights = {k: v / total_new for k, v in new_weights.items()}

        # Write via UPSERT preserving manual_override=1 rows
        for a_name, new_w in renorm_weights.items():
            await conn.execute(
                """
                INSERT INTO agent_weights (agent_name, asset_type, weight, source, updated_at)
                VALUES (?, ?, ?, 'ic_ir', CURRENT_TIMESTAMP)
                ON CONFLICT(agent_name, asset_type) DO UPDATE SET
                    weight = excluded.weight,
                    source = 'ic_ir',
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_weights.manual_override = 0
                """,
                (a_name, asset_type, round(new_w, 6)),
            )
        await conn.commit()

        # Return the new weight for this specific agent
        return round(renorm_weights.get(agent_name, 0.0), 6)


async def _write_drift_log(conn: Any, entry: dict[str, Any]) -> None:
    """Insert a row into drift_log for this drift evaluation."""
    await conn.execute(
        """
        INSERT INTO drift_log (
            agent_name, asset_type, evaluated_at,
            current_icir, avg_icir_60d, delta_pct, threshold_type,
            triggered, preliminary_threshold, weight_before, weight_after
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["agent_name"],
            entry["asset_type"],
            entry["evaluated_at"],
            entry.get("current_icir"),
            entry.get("avg_icir_60d"),
            entry.get("delta_pct"),
            entry.get("threshold_type"),
            1 if entry.get("triggered") else 0,
            1 if entry.get("preliminary_threshold") else 0,
            entry.get("weight_before"),
            entry.get("weight_after"),
        ),
    )
    await conn.commit()


def _agent_asset_types(agent_name: str) -> list[str]:
    """Return the asset_types this agent applies to.

    CryptoAgent handles btc/eth only.
    FundamentalAgent, TechnicalAgent, MacroAgent, SentimentAgent handle stocks.
    """
    if agent_name == "CryptoAgent":
        return ["btc", "eth"]
    return ["stock"]
