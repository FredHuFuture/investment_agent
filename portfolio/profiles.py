"""Portfolio profile management for multi-portfolio support."""
from __future__ import annotations

from pathlib import Path

import aiosqlite


class PortfolioProfileManager:
    """CRUD operations for portfolio profiles (Sprint 13.4)."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    async def create_profile(
        self,
        name: str,
        description: str = "",
        initial_cash: float = 0,
    ) -> dict:
        """Create a new portfolio profile. Returns the created profile dict."""
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            try:
                cursor = await conn.execute(
                    """
                    INSERT INTO portfolios (name, description, cash)
                    VALUES (?, ?, ?)
                    """,
                    (name, description, initial_cash),
                )
                await conn.commit()
                profile_id = int(cursor.lastrowid)
            except aiosqlite.IntegrityError:
                raise ValueError(f"A portfolio with the name '{name}' already exists.")

            return await self._fetch_profile(conn, profile_id)

    async def list_profiles(self) -> list[dict]:
        """Return all portfolio profiles ordered by id."""
        async with aiosqlite.connect(self._db_path) as conn:
            rows = await (
                await conn.execute(
                    """
                    SELECT id, name, description, cash, created_at, is_default
                    FROM portfolios
                    ORDER BY id ASC
                    """
                )
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]

    async def get_profile(self, profile_id: int) -> dict | None:
        """Return a single portfolio profile or None if not found."""
        async with aiosqlite.connect(self._db_path) as conn:
            return await self._fetch_profile(conn, profile_id)

    async def update_profile(
        self,
        profile_id: int,
        name: str | None = None,
        description: str | None = None,
    ) -> bool:
        """Update name and/or description of a profile. Returns True if updated."""
        updates: list[str] = []
        params: list[object] = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if not updates:
            return False

        params.append(profile_id)
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")
            try:
                cursor = await conn.execute(
                    f"UPDATE portfolios SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                await conn.commit()
            except aiosqlite.IntegrityError:
                raise ValueError(f"A portfolio with the name '{name}' already exists.")
            return cursor.rowcount > 0

    async def delete_profile(self, profile_id: int) -> bool:
        """Delete a portfolio profile only if it has no positions.

        Returns True if deleted, raises ValueError if the profile has positions
        or is the default profile.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")

            # Check if profile exists
            row = await (
                await conn.execute(
                    "SELECT is_default FROM portfolios WHERE id = ?", (profile_id,)
                )
            ).fetchone()
            if row is None:
                return False

            if row[0] == 1:
                raise ValueError("Cannot delete the default portfolio.")

            # Check for linked positions (open or closed)
            pos_count = await (
                await conn.execute(
                    "SELECT COUNT(*) FROM active_positions WHERE portfolio_id = ?",
                    (profile_id,),
                )
            ).fetchone()
            if pos_count and pos_count[0] > 0:
                raise ValueError(
                    "Cannot delete portfolio with existing positions. "
                    "Remove or transfer positions first."
                )

            cursor = await conn.execute(
                "DELETE FROM portfolios WHERE id = ?", (profile_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def set_default(self, profile_id: int) -> bool:
        """Set the given profile as the default portfolio.

        Returns True if the profile was found and set as default.
        """
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")

            # Verify profile exists
            row = await (
                await conn.execute(
                    "SELECT id FROM portfolios WHERE id = ?", (profile_id,)
                )
            ).fetchone()
            if row is None:
                return False

            # Clear current default(s) and set new one
            await conn.execute("UPDATE portfolios SET is_default = 0")
            await conn.execute(
                "UPDATE portfolios SET is_default = 1 WHERE id = ?", (profile_id,)
            )
            await conn.commit()
            return True

    async def get_default_profile_id(self) -> int:
        """Return the id of the default portfolio. Falls back to 1 if none marked."""
        async with aiosqlite.connect(self._db_path) as conn:
            row = await (
                await conn.execute(
                    "SELECT id FROM portfolios WHERE is_default = 1 LIMIT 1"
                )
            ).fetchone()
            if row is not None:
                return int(row[0])
            return 1

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_profile(
        self, conn: aiosqlite.Connection, profile_id: int
    ) -> dict | None:
        row = await (
            await conn.execute(
                """
                SELECT id, name, description, cash, created_at, is_default
                FROM portfolios WHERE id = ?
                """,
                (profile_id,),
            )
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    @staticmethod
    def _row_to_dict(row: tuple) -> dict:
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "cash": float(row[3]),
            "created_at": row[4],
            "is_default": bool(row[5]),
        }
