"""Journal analytics: compute win-rate-by-tag from lesson annotations."""
from __future__ import annotations

import aiosqlite


class JournalAnalytics:
    """Connects lesson annotations to trade outcomes for pattern analysis."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def get_lesson_tag_stats(self) -> list[dict]:
        """For each lesson tag, compute win/loss stats against closed positions.

        Returns a list of dicts with keys:
            tag, count, win_count, loss_count, win_rate, avg_return_pct
        """
        sql = """\
            SELECT
                ta.lesson_tag                                    AS tag,
                COUNT(*)                                         AS count,
                SUM(CASE WHEN ap.realized_pnl > 0 THEN 1 ELSE 0 END) AS win_count,
                SUM(CASE WHEN ap.realized_pnl <= 0 THEN 1 ELSE 0 END) AS loss_count,
                ROUND(
                    SUM(CASE WHEN ap.realized_pnl > 0 THEN 1.0 ELSE 0.0 END)
                    / COUNT(*) * 100, 1
                )                                                AS win_rate,
                ROUND(
                    AVG(
                        CASE WHEN ap.avg_cost > 0
                            THEN ap.realized_pnl / (ap.quantity * ap.avg_cost) * 100
                            ELSE 0
                        END
                    ), 2
                )                                                AS avg_return_pct
            FROM trade_annotations ta
            JOIN active_positions ap
                ON ta.position_ticker = ap.ticker
            WHERE ap.status = 'closed'
              AND ta.lesson_tag IS NOT NULL
            GROUP BY ta.lesson_tag
            ORDER BY count DESC
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql)
            rows = await cursor.fetchall()

        return [
            {
                "tag": row["tag"],
                "count": row["count"],
                "win_count": row["win_count"],
                "loss_count": row["loss_count"],
                "win_rate": row["win_rate"],
                "avg_return_pct": row["avg_return_pct"],
            }
            for row in rows
        ]
