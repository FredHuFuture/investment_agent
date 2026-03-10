from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from data_providers.factory import get_provider
from db.database import DEFAULT_DB_PATH
from monitoring.checker import check_position
from monitoring.models import Alert
from monitoring.store import AlertStore
from portfolio.manager import PortfolioManager


class PortfolioMonitor:
    """One-shot portfolio health check.

    Loads portfolio, fetches current prices, checks all exit triggers,
    saves alerts, saves portfolio snapshot.
    """

    def __init__(self, db_path: str = str(DEFAULT_DB_PATH)) -> None:
        self._db_path = db_path

    async def run_check(self) -> dict[str, Any]:
        """Run full portfolio health check.

        Returns dict with:
            checked_positions: int
            alerts: list[dict]       # all alerts generated
            snapshot_saved: bool
            warnings: list[str]      # non-fatal issues (e.g. price fetch failed)
        """
        pm = PortfolioManager(self._db_path)
        portfolio = await pm.load_portfolio()

        all_alerts: list[Alert] = []
        warnings: list[str] = []
        checked_positions = 0

        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute("PRAGMA foreign_keys=ON;")

            for position in portfolio.positions:
                # Fetch current price
                try:
                    provider = get_provider(position.asset_type)
                    current_price = await provider.get_current_price(position.ticker)
                    if current_price is None or current_price <= 0:
                        raise ValueError(f"Invalid price returned: {current_price}")
                except Exception as exc:
                    warnings.append(f"{position.ticker}: price fetch failed — {exc}")
                    continue

                # Fetch stop_loss / target_price from positions_thesis if linked
                expected_stop_loss: float | None = None
                expected_target_price: float | None = None
                if position.original_analysis_id is not None:
                    thesis_row = await (
                        await conn.execute(
                            """
                            SELECT expected_stop_loss, expected_target_price
                            FROM positions_thesis
                            WHERE id = ?
                            """,
                            (position.original_analysis_id,),
                        )
                    ).fetchone()
                    if thesis_row is not None:
                        expected_stop_loss = (
                            float(thesis_row[0]) if thesis_row[0] is not None else None
                        )
                        expected_target_price = (
                            float(thesis_row[1]) if thesis_row[1] is not None else None
                        )

                position_alerts = check_position(
                    position, current_price, expected_stop_loss, expected_target_price
                )
                all_alerts.extend(position_alerts)
                checked_positions += 1

            # Save alerts in one transaction
            if all_alerts:
                store = AlertStore(conn)
                await store.save_alerts(all_alerts)

            # Save portfolio snapshot
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                """
                INSERT INTO portfolio_snapshots (
                    timestamp, total_value, cash, positions_json, trigger_event
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    now,
                    portfolio.total_value,
                    portfolio.cash,
                    json.dumps([p.to_dict() for p in portfolio.positions]),
                    "daily_check",
                ),
            )
            await conn.commit()

        return {
            "checked_positions": checked_positions,
            "alerts": [a.to_dict() for a in all_alerts],
            "snapshot_saved": True,
            "warnings": warnings,
        }
