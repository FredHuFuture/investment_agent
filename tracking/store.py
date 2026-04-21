from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from engine.aggregator import AggregatedSignal


# ---------------------------------------------------------------------------
# Backtest corpus read helpers (SIG-02, SIG-03 — Plan 02-03)
# ---------------------------------------------------------------------------


async def _get_backtest_signals_by_agent(
    db_path: Path,
    agent_name: str,
    horizon: str = "5d",
) -> list[dict]:
    """Read per-agent backtest signals with forward returns from backtest_signal_history.

    Returns list of {ticker, signal_date, raw_score, signal, confidence,
                      forward_return} dicts.
    forward_return is from the requested horizon column.
    Rows with NULL forward_return are excluded.
    """
    col = "forward_return_5d" if horizon == "5d" else "forward_return_21d"
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        rows = await (
            await conn.execute(
                f"""
                SELECT ticker, signal_date, raw_score, signal, confidence,
                       {col} AS forward_return
                FROM backtest_signal_history
                WHERE agent_name = ? AND {col} IS NOT NULL
                ORDER BY signal_date ASC
                """,
                (agent_name,),
            )
        ).fetchall()
    return [dict(r) for r in rows]


class SignalStore:
    """Persist and query signal history."""

    def __init__(self, db: str | Path | aiosqlite.Connection) -> None:
        if isinstance(db, aiosqlite.Connection):
            self._connection: aiosqlite.Connection | None = db
            self._db_path: Path | None = None
        else:
            self._connection = None
            self._db_path = Path(db)

    async def _with_conn(self, func):
        if self._connection is not None:
            return await func(self._connection)
        if self._db_path is None:
            raise RuntimeError("SignalStore is missing both connection and database path.")
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            return await func(conn)

    async def save_signal(
        self,
        signal: AggregatedSignal,
        thesis_id: int | None = None,
    ) -> int:
        """Persist an AggregatedSignal to signal_history. Returns row id."""
        raw_score = signal.metrics.get("raw_score", 0.0)
        consensus_score = signal.metrics.get("consensus_score", 0.0)
        agent_signals_json = json.dumps([a.to_dict() for a in signal.agent_signals])
        warnings_json = json.dumps(signal.warnings) if signal.warnings else None
        regime_str = signal.regime.value if signal.regime else None

        async def _op(conn: aiosqlite.Connection) -> int:
            cursor = await conn.execute(
                """
                INSERT INTO signal_history (
                    ticker, asset_type, final_signal, final_confidence,
                    regime, raw_score, consensus_score,
                    agent_signals_json, reasoning, warnings_json, thesis_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.ticker,
                    signal.asset_type,
                    signal.final_signal.value,
                    signal.final_confidence,
                    regime_str,
                    raw_score,
                    consensus_score,
                    agent_signals_json,
                    signal.reasoning,
                    warnings_json,
                    thesis_id,
                ),
            )
            await conn.commit()
            return int(cursor.lastrowid)

        return await self._with_conn(_op)

    async def resolve_outcome(
        self,
        signal_id: int,
        outcome: str,
        return_pct: float | None = None,
    ) -> None:
        """Update a signal's outcome after trade resolution."""
        resolved_at = datetime.now(timezone.utc).isoformat()

        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                """
                UPDATE signal_history
                SET outcome = ?,
                    outcome_return_pct = ?,
                    outcome_resolved_at = ?
                WHERE id = ?
                """,
                (outcome, return_pct, resolved_at, signal_id),
            )
            await conn.commit()

        await self._with_conn(_op)

    async def resolve_from_thesis(self, thesis_id: int) -> None:
        """Auto-resolve outcome from trade_executions data.

        Looks up the signal_history row linked to this thesis_id.
        Queries trade_executions to determine if position is closed.
        """
        async def _op(conn: aiosqlite.Connection) -> None:
            # Find signal row for this thesis
            signal_row = await (
                await conn.execute(
                    """
                    SELECT id, final_signal
                    FROM signal_history
                    WHERE thesis_id = ?
                    LIMIT 1
                    """,
                    (thesis_id,),
                )
            ).fetchone()
            if signal_row is None:
                return

            signal_id = int(signal_row[0])
            final_signal = str(signal_row[1])

            # Query trade executions
            exec_rows = await (
                await conn.execute(
                    """
                    SELECT action, quantity, executed_price
                    FROM trade_executions
                    WHERE thesis_id = ?
                    ORDER BY id ASC
                    """,
                    (thesis_id,),
                )
            ).fetchall()

            if not exec_rows:
                await _update_outcome(conn, signal_id, "SKIPPED", None)
                return

            buy_qty = 0.0
            buy_value = 0.0
            sell_qty = 0.0
            sell_value = 0.0
            for action, quantity, executed_price in exec_rows:
                qty = float(quantity)
                price = float(executed_price)
                if str(action).upper() == "BUY":
                    buy_qty += qty
                    buy_value += qty * price
                elif str(action).upper() == "SELL":
                    sell_qty += qty
                    sell_value += qty * price

            if buy_qty <= 0:
                await _update_outcome(conn, signal_id, "SKIPPED", None)
                return

            # Position is closed when total sells >= total buys
            if sell_qty >= buy_qty and sell_qty > 0:
                avg_buy = buy_value / buy_qty
                avg_sell = sell_value / sell_qty
                actual_return_pct = (avg_sell - avg_buy) / avg_buy if avg_buy != 0 else 0.0

                # Determine WIN/LOSS based on signal direction
                if final_signal == "BUY":
                    outcome = "WIN" if actual_return_pct > 0 else "LOSS"
                elif final_signal == "SELL":
                    # SELL is correct if the price went down (negative return = WIN)
                    outcome = "WIN" if actual_return_pct < 0 else "LOSS"
                else:
                    # HOLD — mark as OPEN if position was taken
                    outcome = "OPEN"
                    actual_return_pct = None

                await _update_outcome(conn, signal_id, outcome, actual_return_pct)
            else:
                # Position still open
                await _update_outcome(conn, signal_id, "OPEN", None)

        await self._with_conn(_op)

    async def get_signal_history(
        self,
        ticker: str | None = None,
        signal: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Query recent signals, optionally filtered. Returns parsed dicts."""
        async def _op(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
            conditions: list[str] = []
            params: list[Any] = []
            if ticker is not None:
                conditions.append("ticker = ?")
                params.append(ticker)
            if signal is not None:
                conditions.append("final_signal = ?")
                params.append(signal)
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)
            rows = await (
                await conn.execute(
                    f"""
                    SELECT id, ticker, asset_type, final_signal, final_confidence,
                           regime, raw_score, consensus_score,
                           agent_signals_json, reasoning, warnings_json,
                           thesis_id, outcome, outcome_return_pct,
                           outcome_resolved_at, created_at
                    FROM signal_history
                    {where}
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    params,
                )
            ).fetchall()
            return [_row_to_dict(row) for row in rows]

        return await self._with_conn(_op)

    async def get_signal_count(self, lookback: int = 100) -> int:
        """Count total signals in lookback window (all outcomes, including NULL/OPEN/SKIPPED)."""

        async def _op(conn: aiosqlite.Connection) -> int:
            row = await (
                await conn.execute(
                    """
                    SELECT COUNT(*) FROM (
                        SELECT id FROM signal_history
                        ORDER BY created_at DESC
                        LIMIT ?
                    )
                    """,
                    (lookback,),
                )
            ).fetchone()
            return int(row[0]) if row else 0

        return await self._with_conn(_op)

    async def get_resolved_signals(
        self,
        lookback: int = 100,
    ) -> list[dict[str, Any]]:
        """Get signals with WIN/LOSS outcomes for accuracy computation."""
        async def _op(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
            rows = await (
                await conn.execute(
                    """
                    SELECT id, ticker, asset_type, final_signal, final_confidence,
                           regime, raw_score, consensus_score,
                           agent_signals_json, reasoning, warnings_json,
                           thesis_id, outcome, outcome_return_pct,
                           outcome_resolved_at, created_at
                    FROM signal_history
                    WHERE outcome IN ('WIN', 'LOSS')
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (lookback,),
                )
            ).fetchall()
            return [_row_to_dict(row) for row in rows]

        return await self._with_conn(_op)

    # -----------------------------------------------------------------------
    # Backtest corpus readers (SIG-02 / SIG-03 — Plan 02-03)
    # -----------------------------------------------------------------------

    async def get_backtest_signals_by_agent(
        self,
        agent_name: str,
        horizon: str = "5d",
    ) -> list[dict]:
        """Read per-agent backtest signals with forward returns.

        Returns list of {ticker, signal_date, raw_score, signal,
                          confidence, forward_return} dicts.
        forward_return is from the requested horizon column.
        Rows with NULL forward_return are excluded.
        """
        if self._db_path is None:
            # Fallback path: use module-level helper via a temp file path
            # This branch is taken when store was constructed with a live connection.
            raise RuntimeError(
                "get_backtest_signals_by_agent requires a db_path-based SignalStore "
                "(not a live aiosqlite.Connection). Construct SignalStore(str(db_path))."
            )
        return await _get_backtest_signals_by_agent(self._db_path, agent_name, horizon)

    async def get_backtest_corpus_metadata(self) -> dict:
        """Return corpus-level metadata for the calibration API.

        Returns date_range, total_observations, tickers_covered,
        n_agents, and survivorship_bias_warning.
        """
        if self._db_path is None:
            raise RuntimeError(
                "get_backtest_corpus_metadata requires a db_path-based SignalStore."
            )
        async with aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            meta_row = await (
                await conn.execute(
                    """
                    SELECT MIN(signal_date) AS min_date,
                           MAX(signal_date) AS max_date,
                           COUNT(*) AS total,
                           COUNT(DISTINCT ticker) AS n_tickers,
                           COUNT(DISTINCT agent_name) AS n_agents
                    FROM backtest_signal_history
                    """
                )
            ).fetchone()
            tickers_rows = await (
                await conn.execute(
                    "SELECT DISTINCT ticker FROM backtest_signal_history ORDER BY ticker"
                )
            ).fetchall()
        return {
            "date_range": (
                [meta_row["min_date"], meta_row["max_date"]]
                if meta_row and meta_row["min_date"]
                else [None, None]
            ),
            "total_observations": (meta_row["total"] or 0) if meta_row else 0,
            "tickers_covered": [t["ticker"] for t in tickers_rows],
            "n_agents": (meta_row["n_agents"] or 0) if meta_row else 0,
            "survivorship_bias_warning": True,  # AP-04: documented limitation
        }


async def _update_outcome(
    conn: aiosqlite.Connection,
    signal_id: int,
    outcome: str,
    return_pct: float | None,
) -> None:
    resolved_at = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        """
        UPDATE signal_history
        SET outcome = ?,
            outcome_return_pct = ?,
            outcome_resolved_at = ?
        WHERE id = ?
        """,
        (outcome, return_pct, resolved_at, signal_id),
    )
    await conn.commit()


def _row_to_dict(row: tuple) -> dict[str, Any]:
    agent_signals_json = row[8]
    warnings_json = row[10]
    return {
        "id": row[0],
        "ticker": row[1],
        "asset_type": row[2],
        "final_signal": row[3],
        "final_confidence": row[4],
        "regime": row[5],
        "raw_score": row[6],
        "consensus_score": row[7],
        "agent_signals": json.loads(agent_signals_json) if agent_signals_json else [],
        "reasoning": row[9],
        "warnings": json.loads(warnings_json) if warnings_json else [],
        "thesis_id": row[11],
        "outcome": row[12],
        "outcome_return_pct": row[13],
        "outcome_resolved_at": row[14],
        "created_at": row[15],
    }
