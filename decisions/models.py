# decisions/models.py
"""Decision-layer domain model + shared low-level helpers.

Task 5 introduces the helpers (serialization, hashing, time). Task 6 appends
the enum, error type, proposal-hash function, and ProposedAction dataclass.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
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
