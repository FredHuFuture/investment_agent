"""Simple async connection pool for aiosqlite.

Designed for the daemon's long-running process: connections are created
lazily, reused across operations, and WAL mode is enabled on each one.

Usage
-----
    # At startup:
    await db_pool.init(db_path)

    # In any async function:
    async with db_pool.connection() as conn:
        await conn.execute(...)

    # At shutdown:
    await db_pool.close_all()
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

logger = logging.getLogger(__name__)


class DatabasePool:
    """Async connection pool for a single SQLite database file.

    Connections are created lazily up to *pool_size*.  When all connections
    are in use the caller waits until one is returned.
    """

    def __init__(self, pool_size: int = 5) -> None:
        self._pool_size = pool_size
        self._db_path: Path | None = None
        self._pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue()
        self._all_connections: list[aiosqlite.Connection] = []
        self._current_size = 0
        self._lock = asyncio.Lock()
        self._initialised = False

    async def init(self, db_path: str | Path) -> None:
        """Set the database path.  Call once at process startup.

        If the pool was previously initialised with a different path, all
        existing connections are closed first so stale handles are never
        reused.
        """
        new_path = Path(db_path)
        if self._initialised and self._db_path != new_path:
            await self.close_all()
        self._db_path = new_path
        self._initialised = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _new_connection(self) -> aiosqlite.Connection:
        """Open a fresh connection and configure it."""
        assert self._db_path is not None, "DatabasePool.init() must be called first"
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        await conn.execute("PRAGMA foreign_keys=ON;")
        self._all_connections.append(conn)
        logger.debug("DatabasePool: opened connection #%d", len(self._all_connections))
        return conn

    async def get_connection(self) -> aiosqlite.Connection:
        """Return a connection from the pool, creating one if capacity allows."""
        # Fast path: grab an idle connection
        try:
            return self._pool.get_nowait()
        except asyncio.QueueEmpty:
            pass

        # Slow path: create a new connection if under capacity
        async with self._lock:
            if self._current_size < self._pool_size:
                self._current_size += 1
                return await self._new_connection()

        # At capacity — wait for a connection to be released
        return await self._pool.get()

    async def release(self, conn: aiosqlite.Connection) -> None:
        """Return *conn* to the pool for reuse."""
        await self._pool.put(conn)

    # ------------------------------------------------------------------
    # Public context manager
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Async context manager that borrows and returns a connection.

        Example::

            async with pool.connection() as conn:
                await conn.execute("SELECT 1")
        """
        conn = await self.get_connection()
        try:
            yield conn
        except Exception:
            # On error, close the connection rather than recycling it —
            # it may be in an inconsistent transaction state.
            try:
                await conn.close()
            except Exception:
                pass
            self._all_connections = [c for c in self._all_connections if c is not conn]
            self._current_size -= 1
            raise
        else:
            await self.release(conn)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def close_all(self) -> None:
        """Close every connection in the pool.  Call at process shutdown."""
        # Drain idle connections from the queue first
        while True:
            try:
                conn = self._pool.get_nowait()
                await conn.close()
            except asyncio.QueueEmpty:
                break

        # Close any that are still checked out
        for conn in list(self._all_connections):
            try:
                await conn.close()
            except Exception:
                pass

        self._all_connections.clear()
        self._current_size = 0
        logger.debug("DatabasePool: all connections closed")


# ---------------------------------------------------------------------------
# Module-level singleton — initialise once at startup with db_pool.init(path)
# ---------------------------------------------------------------------------

db_pool = DatabasePool(pool_size=5)
