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
