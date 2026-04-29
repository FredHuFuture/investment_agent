"""Unit tests for SimfinStatementCache (Phase 8 DATA-v2-02).

Verifies:
- get/set round-trip with key tuple (ticker, statement, period, fyear, asreported)
- Different asreported values write to different files (no collision)
- 24h TTL expiry returns None
- Path-traversal mitigation — adversarial ticker names cannot escape cache dir
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import pytest

from data_providers.simfin_cache import SimfinStatementCache


# ============================================================================
# T1: Empty cache returns None on miss
# ============================================================================


def test_get_returns_none_on_miss(tmp_path: Path) -> None:
    cache = SimfinStatementCache(cache_dir=tmp_path)
    result = cache.get("AAPL", statement="pl", period="q1", fyear=2024)
    assert result is None


# ============================================================================
# T2: set then get round-trip returns equivalent DataFrame
# ============================================================================


def test_set_then_get_round_trip(tmp_path: Path) -> None:
    cache = SimfinStatementCache(cache_dir=tmp_path)
    df = pd.DataFrame(
        [
            {"Revenue": 100_000_000, "Net Income": 12_000_000},
            {"Revenue": 110_000_000, "Net Income": 13_000_000},
        ]
    )
    cache.set(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=True, df=df
    )
    result = cache.get(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=True
    )
    assert result is not None
    assert len(result) == 2
    assert result.iloc[0]["Revenue"] == 100_000_000


# ============================================================================
# T3: asreported=True vs False are distinct cache entries
# ============================================================================


def test_asreported_true_and_false_dont_collide(tmp_path: Path) -> None:
    cache = SimfinStatementCache(cache_dir=tmp_path)
    df_true = pd.DataFrame([{"Revenue": 100_000_000}])
    df_false = pd.DataFrame([{"Revenue": 115_000_000}])
    cache.set(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=True, df=df_true
    )
    cache.set(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=False, df=df_false
    )
    result_true = cache.get(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=True
    )
    result_false = cache.get(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=False
    )
    assert result_true is not None
    assert result_false is not None
    assert result_true.iloc[0]["Revenue"] == 100_000_000
    assert result_false.iloc[0]["Revenue"] == 115_000_000


# ============================================================================
# T4: TTL expiry returns None (24h default)
# ============================================================================


def test_ttl_expiry_returns_none(tmp_path: Path) -> None:
    cache = SimfinStatementCache(cache_dir=tmp_path)
    df = pd.DataFrame([{"Revenue": 100_000_000}])
    cache.set("AAPL", statement="pl", period="q1", fyear=2024, asreported=True, df=df)

    # Manually backdate the file mtime to 25 hours ago
    path = cache._path_for("AAPL", "pl", "q1", 2024, True)
    old_time = time.time() - (25 * 3600)
    os.utime(path, (old_time, old_time))

    result = cache.get(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=True
    )
    assert result is None  # expired


# ============================================================================
# T5: TTL parameter override
# ============================================================================


def test_ttl_override_short_window(tmp_path: Path) -> None:
    cache = SimfinStatementCache(cache_dir=tmp_path)
    df = pd.DataFrame([{"Revenue": 100_000_000}])
    cache.set("AAPL", statement="pl", period="q1", fyear=2024, asreported=True, df=df)

    # Backdate to 2 seconds ago, request a 1-second TTL → expired
    path = cache._path_for("AAPL", "pl", "q1", 2024, True)
    old_time = time.time() - 2
    os.utime(path, (old_time, old_time))

    result = cache.get(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=True, ttl=1.0
    )
    assert result is None


# ============================================================================
# T6: invalidate() removes cache entry
# ============================================================================


def test_invalidate_removes_entry(tmp_path: Path) -> None:
    cache = SimfinStatementCache(cache_dir=tmp_path)
    df = pd.DataFrame([{"Revenue": 100_000_000}])
    cache.set("AAPL", statement="pl", period="q1", fyear=2024, asreported=True, df=df)
    assert cache.invalidate(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=True
    )
    result = cache.get(
        "AAPL", statement="pl", period="q1", fyear=2024, asreported=True
    )
    assert result is None


def test_invalidate_returns_false_on_miss(tmp_path: Path) -> None:
    cache = SimfinStatementCache(cache_dir=tmp_path)
    assert (
        cache.invalidate(
            "MISSING", statement="pl", period="q1", fyear=2024, asreported=True
        )
        is False
    )


# ============================================================================
# T7: Path-traversal mitigation — adversarial ticker can't escape cache dir
# (T-08-02-05)
# ============================================================================


def test_adversarial_ticker_sanitized(tmp_path: Path) -> None:
    """T-08-02-05 — '../../etc/passwd' must not escape cache_dir.

    The regex preserves dots (so 'BRK.B' tickers work) but strips the path
    separators '/' and '\\\\'. With separators gone the resulting filename is
    a single dotted blob inside the cache dir — no traversal possible.
    """
    cache = SimfinStatementCache(cache_dir=tmp_path)
    df = pd.DataFrame([{"Revenue": 1}])
    cache.set(
        "../../etc/passwd",
        statement="pl",
        period="q1",
        fyear=2024,
        asreported=True,
        df=df,
    )
    # Final filename has dashes substituted; only one file exists, inside tmp_path
    files = list(tmp_path.glob("*.parquet"))
    assert len(files) == 1, f"Adversarial ticker escaped cache dir: {files}"
    fname = files[0].name
    # Path separators are the actual escape vector — they MUST be gone
    assert "/" not in fname
    assert "\\" not in fname
    # The file's resolved path stays inside tmp_path (cannot traverse out)
    assert files[0].resolve().is_relative_to(tmp_path.resolve())


# ============================================================================
# T8: stats() returns hit/miss accounting
# ============================================================================


def test_stats_tracks_hits_and_misses(tmp_path: Path) -> None:
    cache = SimfinStatementCache(cache_dir=tmp_path)
    cache.get("AAPL", "pl", "q1", 2024, True)  # miss
    df = pd.DataFrame([{"Revenue": 1}])
    cache.set("AAPL", "pl", "q1", 2024, True, df)
    cache.get("AAPL", "pl", "q1", 2024, True)  # hit
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["total"] == 2
    assert stats["hit_rate"] == 0.5
