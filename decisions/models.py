# decisions/models.py
"""Decision-layer domain model + shared low-level helpers.

Task 5 introduces the helpers (serialization, hashing, time). Task 6 appends
the enum, error type, proposal-hash function, and ProposedAction dataclass.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, tight separators, ASCII-escaped."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_past(iso_ts: str) -> bool:
    """True if the ISO-8601 UTC timestamp is at or before 'now' (UTC)."""
    return datetime.now(timezone.utc) >= datetime.fromisoformat(iso_ts)


class DecisionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"


class DecisionError(Exception):
    """Domain error carrying an API error code and an HTTP status.

    Lets the manager raise once and have both the API route and the CLI map it
    to the right status code / exit behaviour without duplicating gate logic.
    """

    def __init__(self, code: str, message: str, http_status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def default_quantity() -> float:
    return float(os.getenv("DECISION_DEFAULT_QUANTITY", "1.0"))


def ttl_hours() -> int:
    return int(os.getenv("DECISION_PROPOSAL_TTL_HOURS", "24"))


def compute_proposal_hash(
    ticker: str, action: str, quantity: float | None, signal: Any
) -> str:
    """sha256 over ONLY the decision-binding fields — never the full mutable
    signal dict — so the same decision always hashes identically.
    """
    payload = canonical_json({
        "ticker": ticker,
        "action": action,
        "quantity": quantity,
        "final_signal": signal.final_signal.value,
        "final_confidence": round(signal.final_confidence, 2),
        "regime": signal.regime.value if signal.regime else None,
    })
    return sha256_hex(payload)


@dataclass
class ProposedAction:
    id: int | None
    ticker: str
    asset_type: str
    action: str
    quantity: float | None
    source_signal_json: str
    reasoning: str
    proposal_hash: str
    status: str
    valid_until: str
    actor: str | None
    decided_at: str | None
    decision_note: str | None
    approved_proposal_hash: str | None
    execution_report_json: str | None
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> "ProposedAction":
        return cls(
            id=row["id"],
            ticker=row["ticker"],
            asset_type=row["asset_type"],
            action=row["action"],
            quantity=row["quantity"],
            source_signal_json=row["source_signal_json"],
            reasoning=row["reasoning"],
            proposal_hash=row["proposal_hash"],
            status=row["status"],
            valid_until=row["valid_until"],
            actor=row["actor"],
            decided_at=row["decided_at"],
            decision_note=row["decision_note"],
            approved_proposal_hash=row["approved_proposal_hash"],
            execution_report_json=row["execution_report_json"],
            created_at=row["created_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "asset_type": self.asset_type,
            "action": self.action,
            "quantity": self.quantity,
            "reasoning": self.reasoning,
            "proposal_hash": self.proposal_hash,
            "status": self.status,
            "valid_until": self.valid_until,
            "actor": self.actor,
            "decided_at": self.decided_at,
            "decision_note": self.decision_note,
            "approved_proposal_hash": self.approved_proposal_hash,
            "execution_report": (
                json.loads(self.execution_report_json)
                if self.execution_report_json else None
            ),
            "source_signal": json.loads(self.source_signal_json),
            "created_at": self.created_at,
        }

    def to_summary(self) -> dict[str, Any]:
        """List-view shape: omit the heavyweight source_signal blob."""
        d = self.to_dict()
        d.pop("source_signal", None)
        return d
