"""Tests for Task 010: check_position pure function (no DB, no mocks)."""
from __future__ import annotations

from datetime import date, timedelta

from portfolio.models import Position
from monitoring.checker import check_position


def _make_position(
    ticker: str = "TEST",
    asset_type: str = "stock",
    avg_cost: float = 100.0,
    entry_days_ago: int = 10,
    expected_hold_days: int | None = 30,
    original_analysis_id: int | None = None,
) -> Position:
    entry_date = (date.today() - timedelta(days=entry_days_ago)).isoformat()
    return Position(
        ticker=ticker,
        asset_type=asset_type,
        quantity=10.0,
        avg_cost=avg_cost,
        entry_date=entry_date,
        expected_hold_days=expected_hold_days,
        original_analysis_id=original_analysis_id,
    )


class TestCheckPosition:
    # 1. Stop loss alert
    def test_stop_loss_alert(self) -> None:
        position = _make_position(avg_cost=100.0)
        alerts = check_position(position, current_price=88.0, expected_stop_loss=90.0)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "STOP_LOSS_HIT"
        assert alerts[0].severity == "CRITICAL"
        assert alerts[0].ticker == "TEST"
        assert alerts[0].trigger_price == 90.0
        assert alerts[0].current_price == 88.0

    # 2. Target hit alert
    def test_target_hit_alert(self) -> None:
        position = _make_position(avg_cost=100.0)
        alerts = check_position(position, current_price=125.0, expected_target_price=120.0)
        assert len(alerts) == 1
        assert alerts[0].alert_type == "TARGET_HIT"
        assert alerts[0].severity == "INFO"
        assert alerts[0].trigger_price == 120.0

    # 3. Time overrun alert
    def test_time_overrun_alert(self) -> None:
        # expected_hold=20, threshold=max(20*1.5, 7)=30. Held 60 days → overrun
        position = _make_position(expected_hold_days=20, entry_days_ago=60)
        alerts = check_position(position, current_price=105.0)
        types = [a.alert_type for a in alerts]
        assert "TIME_OVERRUN" in types
        time_alert = next(a for a in alerts if a.alert_type == "TIME_OVERRUN")
        assert time_alert.severity == "WARNING"

    # 4. Time overrun minimum floor — should NOT fire
    def test_time_overrun_minimum_floor(self) -> None:
        # expected_hold=2, threshold=max(2*1.5, 7)=7. Held 5 days → no alert
        position = _make_position(expected_hold_days=2, entry_days_ago=5)
        alerts = check_position(position, current_price=100.0)
        types = [a.alert_type for a in alerts]
        assert "TIME_OVERRUN" not in types

    # 5. Significant loss (no stop loss set)
    def test_significant_loss_no_stop(self) -> None:
        # −20% < −15% threshold → SIGNIFICANT_LOSS
        position = _make_position(avg_cost=100.0)
        alerts = check_position(position, current_price=80.0)
        types = [a.alert_type for a in alerts]
        assert "SIGNIFICANT_LOSS" in types
        loss_alert = next(a for a in alerts if a.alert_type == "SIGNIFICANT_LOSS")
        assert loss_alert.severity == "HIGH"

    # 5b. Stop loss already fired — SIGNIFICANT_LOSS should NOT fire too
    def test_stop_loss_suppresses_significant_loss(self) -> None:
        position = _make_position(avg_cost=100.0)
        alerts = check_position(position, current_price=80.0, expected_stop_loss=85.0)
        types = [a.alert_type for a in alerts]
        assert "STOP_LOSS_HIT" in types
        assert "SIGNIFICANT_LOSS" not in types

    # 6. Healthy position — no alerts
    def test_healthy_position_no_alerts(self) -> None:
        position = _make_position(
            avg_cost=100.0, expected_hold_days=30, entry_days_ago=10
        )
        alerts = check_position(
            position,
            current_price=105.0,
            expected_stop_loss=90.0,
            expected_target_price=120.0,
        )
        assert alerts == []
