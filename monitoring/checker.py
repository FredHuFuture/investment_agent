from __future__ import annotations

from portfolio.models import Position
from monitoring.models import Alert

# Configurable thresholds
DEFAULT_HOLD_DAYS_FALLBACK = 90       # when expected_hold_days is NULL
TIME_OVERRUN_MULTIPLIER = 1.5
TIME_OVERRUN_MINIMUM_FLOOR = 7        # never fire TIME_OVERRUN before 7 days
SIGNIFICANT_LOSS_THRESHOLD = -0.15   # -15%
SIGNIFICANT_GAIN_THRESHOLD = 0.25    # +25%


def check_position(
    position: Position,
    current_price: float,
    expected_stop_loss: float | None = None,
    expected_target_price: float | None = None,
    enabled_rule_types: set[str] | None = None,
) -> list[Alert]:
    """Check a single position against all exit trigger rules.

    Pure function — no I/O. Returns list of Alert objects (may be empty).

    Args:
        position: Active position from portfolio.
        current_price: Latest market price.
        expected_stop_loss: Stop loss from original thesis (if any).
        expected_target_price: Target price from original thesis (if any).
        enabled_rule_types: None = all rules enabled (backward-compat).
            Set = only rule names in the set will fire. Used by
            PortfolioMonitor to honor alert_rules.enabled toggles (UI-03).
    """

    def _enabled(name: str) -> bool:
        return enabled_rule_types is None or name in enabled_rule_types

    alerts: list[Alert] = []

    raw_pnl_pct = (
        (current_price - position.avg_cost) / position.avg_cost
        if position.avg_cost != 0 else 0.0
    )
    # SHORT positions: negative quantity means price increases are losses.
    # Invert the drift sign so positive price movement shows negative drift.
    is_short = position.quantity < 0
    unrealized_pnl_pct = -raw_pnl_pct if is_short else raw_pnl_pct

    stop_loss_hit = False
    target_hit = False

    # 1. STOP_LOSS_HIT (CRITICAL)
    if _enabled("STOP_LOSS_HIT") and expected_stop_loss is not None and current_price <= expected_stop_loss:
        stop_loss_hit = True
        alerts.append(Alert(
            ticker=position.ticker,
            alert_type="STOP_LOSS_HIT",
            severity="CRITICAL",
            message=(
                f"{position.ticker} hit stop loss ${expected_stop_loss:.2f} "
                f"(current: ${current_price:.2f}, loss: {unrealized_pnl_pct:.1%})"
            ),
            recommended_action="CLOSE POSITION -- stop loss triggered",
            current_price=current_price,
            trigger_price=expected_stop_loss,
        ))

    # 2. TARGET_HIT (INFO)
    if _enabled("TARGET_HIT") and expected_target_price is not None and current_price >= expected_target_price:
        target_hit = True
        alerts.append(Alert(
            ticker=position.ticker,
            alert_type="TARGET_HIT",
            severity="INFO",
            message=(
                f"{position.ticker} reached target ${expected_target_price:.2f} "
                f"(current: ${current_price:.2f}, gain: {unrealized_pnl_pct:.1%})"
            ),
            recommended_action="Consider taking profit -- target reached",
            current_price=current_price,
            trigger_price=expected_target_price,
        ))

    # 3. TIME_OVERRUN (WARNING)
    if _enabled("TIME_OVERRUN"):
        expected_hold = position.expected_hold_days or DEFAULT_HOLD_DAYS_FALLBACK
        threshold = max(expected_hold * TIME_OVERRUN_MULTIPLIER, TIME_OVERRUN_MINIMUM_FLOOR)
        if position.holding_days > threshold:
            multiplier = position.holding_days / expected_hold if expected_hold > 0 else 0.0
            alerts.append(Alert(
                ticker=position.ticker,
                alert_type="TIME_OVERRUN",
                severity="WARNING",
                message=(
                    f"{position.ticker} held {position.holding_days}d vs {expected_hold}d expected "
                    f"({multiplier:.1f}x overrun)"
                ),
                recommended_action="Review: is the original thesis still intact?",
                current_price=current_price,
                trigger_price=None,
            ))

    # 4. SIGNIFICANT_LOSS (HIGH) — skip if STOP_LOSS_HIT already fired
    if _enabled("SIGNIFICANT_LOSS") and not stop_loss_hit and unrealized_pnl_pct < SIGNIFICANT_LOSS_THRESHOLD:
        alerts.append(Alert(
            ticker=position.ticker,
            alert_type="SIGNIFICANT_LOSS",
            severity="HIGH",
            message=(
                f"{position.ticker} unrealized loss {unrealized_pnl_pct:.1%} "
                f"(current: ${current_price:.2f}, avg cost: ${position.avg_cost:.2f})"
            ),
            recommended_action="Review position -- significant unrealized loss",
            current_price=current_price,
            trigger_price=None,
        ))

    # 5. SIGNIFICANT_GAIN (INFO) — skip if TARGET_HIT already fired
    if _enabled("SIGNIFICANT_GAIN") and not target_hit and unrealized_pnl_pct > SIGNIFICANT_GAIN_THRESHOLD:
        alerts.append(Alert(
            ticker=position.ticker,
            alert_type="SIGNIFICANT_GAIN",
            severity="INFO",
            message=(
                f"{position.ticker} unrealized gain {unrealized_pnl_pct:.1%} "
                f"(current: ${current_price:.2f}, avg cost: ${position.avg_cost:.2f})"
            ),
            recommended_action="Consider partial profit-taking",
            current_price=current_price,
            trigger_price=None,
        ))

    return alerts
