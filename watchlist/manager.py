"""Watchlist manager -- CRUD operations for the watchlist table."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from db.database import DEFAULT_DB_PATH


class WatchlistManager:
    """Manages the watchlist SQLite table."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)

    async def add_ticker(
        self,
        ticker: str,
        asset_type: str = "stock",
        notes: str = "",
        target_buy_price: float | None = None,
        alert_below_price: float | None = None,
    ) -> int:
        """Add a ticker to the watchlist. Returns the new row id.

        Raises ``ValueError`` if the ticker already exists.
        """
        ticker = ticker.upper()
        async with aiosqlite.connect(self.db_path) as conn:
            try:
                cursor = await conn.execute(
                    """
                    INSERT INTO watchlist (ticker, asset_type, notes, target_buy_price, alert_below_price)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (ticker, asset_type, notes, target_buy_price, alert_below_price),
                )
                await conn.commit()
                return cursor.lastrowid  # type: ignore[return-value]
            except aiosqlite.IntegrityError:
                raise ValueError(f"Ticker {ticker} is already on the watchlist")

    async def remove_ticker(self, ticker: str) -> bool:
        """Remove a ticker from the watchlist. Returns True if deleted."""
        ticker = ticker.upper()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM watchlist WHERE ticker = ?", (ticker,)
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def get_watchlist(self) -> list[dict]:
        """Return all watchlist items ordered by added_at descending."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute("SELECT * FROM watchlist ORDER BY added_at DESC")
            ).fetchall()
            return [dict(row) for row in rows]

    async def get_ticker(self, ticker: str) -> dict | None:
        """Return a single watchlist item or None."""
        ticker = ticker.upper()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            row = await (
                await conn.execute("SELECT * FROM watchlist WHERE ticker = ?", (ticker,))
            ).fetchone()
            return dict(row) if row else None

    async def update_ticker(self, ticker: str, **kwargs: object) -> bool:
        """Update mutable fields on a watchlist item.

        Allowed fields: notes, target_buy_price, alert_below_price.
        Returns True if the row was found and updated.
        """
        allowed = {"notes", "target_buy_price", "alert_below_price"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False

        ticker = ticker.upper()
        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values())
        values.append(ticker)

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                f"UPDATE watchlist SET {set_clause} WHERE ticker = ?",
                values,
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def update_analysis(
        self, ticker: str, signal: str, confidence: float
    ) -> bool:
        """Store the latest analysis result for a watchlist ticker.

        Returns True if the row was found and updated.
        """
        ticker = ticker.upper()
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                UPDATE watchlist
                SET last_signal = ?, last_confidence = ?, last_analysis_at = ?
                WHERE ticker = ?
                """,
                (signal, confidence, now, ticker),
            )
            await conn.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Active alert query (Sprint 31)
    # ------------------------------------------------------------------

    async def get_tickers_with_active_alerts(self) -> list[dict]:
        """Return watchlist items that have enabled alert configs.

        Joins watchlist + watchlist_alert_configs WHERE enabled=1 and
        returns combined data (watchlist fields + alert config fields).
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    """
                    SELECT
                        w.id,
                        w.ticker,
                        w.asset_type,
                        w.notes,
                        w.target_buy_price,
                        w.alert_below_price,
                        w.added_at,
                        w.last_analysis_at,
                        w.last_signal,
                        w.last_confidence,
                        ac.alert_on_signal_change,
                        ac.min_confidence,
                        ac.alert_on_price_below,
                        ac.enabled,
                        ac.created_at AS config_created_at,
                        ac.updated_at AS config_updated_at
                    FROM watchlist w
                    INNER JOIN watchlist_alert_configs ac ON w.ticker = ac.ticker
                    WHERE ac.enabled = 1
                    ORDER BY w.ticker
                    """
                )
            ).fetchall()
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Alert configuration methods (Sprint 30)
    # ------------------------------------------------------------------

    async def set_alert_config(
        self,
        ticker: str,
        alert_on_signal_change: bool = True,
        min_confidence: float = 60.0,
        alert_on_price_below: float | None = None,
        enabled: bool = True,
    ) -> dict:
        """Upsert alert config for a watchlist ticker."""
        ticker = ticker.upper()
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO watchlist_alert_configs
                    (ticker, alert_on_signal_change, min_confidence,
                     alert_on_price_below, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    alert_on_signal_change = excluded.alert_on_signal_change,
                    min_confidence = excluded.min_confidence,
                    alert_on_price_below = excluded.alert_on_price_below,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    ticker,
                    int(alert_on_signal_change),
                    min_confidence,
                    alert_on_price_below,
                    int(enabled),
                    now,
                    now,
                ),
            )
            await conn.commit()

            conn.row_factory = aiosqlite.Row
            row = await (
                await conn.execute(
                    "SELECT * FROM watchlist_alert_configs WHERE ticker = ?",
                    (ticker,),
                )
            ).fetchone()
            return self._alert_row_to_dict(dict(row))  # type: ignore[arg-type]

    async def get_alert_configs(self) -> list[dict]:
        """Get all alert configurations."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = await (
                await conn.execute(
                    "SELECT * FROM watchlist_alert_configs ORDER BY ticker"
                )
            ).fetchall()
            return [self._alert_row_to_dict(dict(row)) for row in rows]

    async def get_alert_config(self, ticker: str) -> dict | None:
        """Get alert config for a specific ticker."""
        ticker = ticker.upper()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            row = await (
                await conn.execute(
                    "SELECT * FROM watchlist_alert_configs WHERE ticker = ?",
                    (ticker,),
                )
            ).fetchone()
            if row is None:
                return None
            return self._alert_row_to_dict(dict(row))

    @staticmethod
    def _alert_row_to_dict(row: dict) -> dict:
        """Convert DB row integers to booleans for the API response."""
        return {
            "ticker": row["ticker"],
            "alert_on_signal_change": bool(row["alert_on_signal_change"]),
            "min_confidence": row["min_confidence"],
            "alert_on_price_below": row["alert_on_price_below"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
