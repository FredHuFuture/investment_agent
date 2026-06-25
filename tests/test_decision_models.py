# tests/test_decision_models.py
from __future__ import annotations

import pytest

from agents.models import Regime, Signal
from engine.aggregator import AggregatedSignal
from decisions.models import (
    DecisionError,
    DecisionStatus,
    compute_proposal_hash,
    default_quantity,
    ttl_hours,
)


def _signal(conf: float = 72.0, sig: Signal = Signal.BUY) -> AggregatedSignal:
    return AggregatedSignal(
        ticker="AAPL", asset_type="stock", final_signal=sig,
        final_confidence=conf, regime=Regime.RISK_ON, agent_signals=[],
        reasoning="r",
    )


def test_proposal_hash_is_stable_for_same_inputs() -> None:
    s = _signal()
    h1 = compute_proposal_hash("AAPL", "BUY", 1.0, s)
    h2 = compute_proposal_hash("AAPL", "BUY", 1.0, s)
    assert h1 == h2 and len(h1) == 64


def test_proposal_hash_ignores_tiny_confidence_noise() -> None:
    # Rounded to 2 dp -> noise below 0.005 does not change the hash.
    assert compute_proposal_hash("AAPL", "BUY", 1.0, _signal(72.001)) == \
           compute_proposal_hash("AAPL", "BUY", 1.0, _signal(72.0))


def test_proposal_hash_changes_with_binding_field() -> None:
    s = _signal()
    assert compute_proposal_hash("AAPL", "BUY", 1.0, s) != \
           compute_proposal_hash("AAPL", "BUY", 2.0, s)
    assert compute_proposal_hash("AAPL", "BUY", 1.0, s) != \
           compute_proposal_hash("AAPL", "SELL", 1.0, s)


def test_decision_error_carries_code_and_status() -> None:
    err = DecisionError("DECISION_NOT_APPROVED", "nope", 409)
    assert err.code == "DECISION_NOT_APPROVED" and err.http_status == 409


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DECISION_DEFAULT_QUANTITY", raising=False)
    monkeypatch.delenv("DECISION_PROPOSAL_TTL_HOURS", raising=False)
    assert default_quantity() == 1.0
    assert ttl_hours() == 24
    monkeypatch.setenv("DECISION_DEFAULT_QUANTITY", "5")
    monkeypatch.setenv("DECISION_PROPOSAL_TTL_HOURS", "48")
    assert default_quantity() == 5.0
    assert ttl_hours() == 48


def test_status_enum_values() -> None:
    assert DecisionStatus.PENDING.value == "pending"
    assert {s.value for s in DecisionStatus} == {
        "pending", "approved", "rejected", "executed", "expired",
    }
