"""DaemonConfig -- runtime configuration for the monitoring daemon."""
from __future__ import annotations

from dataclasses import dataclass

from db.database import DEFAULT_DB_PATH


@dataclass
class DaemonConfig:
    """Configuration for the monitoring daemon."""

    db_path: str = str(DEFAULT_DB_PATH)

    # Daily check schedule (US/Eastern)
    daily_hour: int = 17           # 5 PM ET -- after market close
    daily_minute: int = 0
    daily_days: str = "mon-fri"    # APScheduler day_of_week format

    # Weekly revaluation schedule
    weekly_day: str = "sat"        # Saturday
    weekly_hour: int = 10          # 10 AM ET
    weekly_minute: int = 0

    # Catalyst scan (stub -- disabled until Task 017)
    catalyst_enabled: bool = False

    # Timezone
    timezone: str = "US/Eastern"

    # Logging
    log_file: str = "data/daemon.log"
    log_level: str = "INFO"
