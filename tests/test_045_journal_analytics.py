"""Tests for JournalAnalytics – win-rate-by-tag computation."""
from __future__ import annotations

import os
import tempfile

import aiosqlite
import pytest

from engine.journal_analytics import JournalAnalytics

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CREATE_POSITIONS = """\
CREATE TABLE active_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    asset_type TEXT NOT NULL DEFAULT 'stock',
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL,
    sector TEXT,
    industry TEXT,
    entry_date TEXT NOT NULL,
    original_analysis_id INTEGER,
    expected_return_pct REAL,
    expected_hold_days INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'open',
    exit_price REAL,
    exit_date TEXT,
    exit_reason TEXT,
    realized_pnl REAL
)
"""

_CREATE_ANNOTATIONS = """\
CREATE TABLE trade_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_ticker TEXT NOT NULL,
    annotation_text TEXT NOT NULL,
    lesson_tag TEXT,
    created_at TEXT DEFAULT (datetime('now'))
)
"""


async def _setup_db(db_path: str) -> None:
    """Create both tables in the test database."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(_CREATE_POSITIONS)
        await conn.execute(_CREATE_ANNOTATIONS)
        await conn.commit()


async def _insert_position(
    db_path: str,
    ticker: str,
    quantity: float,
    avg_cost: float,
    realized_pnl: float,
    status: str = "closed",
) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO active_positions "
            "(ticker, quantity, avg_cost, entry_date, status, realized_pnl, exit_price, exit_date) "
            "VALUES (?, ?, ?, '2024-01-01', ?, ?, ?, '2024-03-01')",
            (ticker, quantity, avg_cost, status, realized_pnl, avg_cost + realized_pnl / quantity),
        )
        await conn.commit()


async def _insert_annotation(
    db_path: str,
    ticker: str,
    text: str,
    tag: str | None,
) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO trade_annotations (position_ticker, annotation_text, lesson_tag) "
            "VALUES (?, ?, ?)",
            (ticker, text, tag),
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_annotations_returns_empty() -> None:
    """When there are no annotations, get_lesson_tag_stats returns []."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        await _setup_db(db_path)
        analytics = JournalAnalytics(db_path)
        result = await analytics.get_lesson_tag_stats()
        assert result == []
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_annotations_without_tags_excluded() -> None:
    """Annotations with lesson_tag = NULL should not appear in stats."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        await _setup_db(db_path)
        await _insert_position(db_path, "AAPL", 10, 150.0, 200.0)
        await _insert_annotation(db_path, "AAPL", "Good trade", None)
        analytics = JournalAnalytics(db_path)
        result = await analytics.get_lesson_tag_stats()
        assert result == []
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_open_positions_excluded() -> None:
    """Annotations on open (non-closed) positions are excluded."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        await _setup_db(db_path)
        await _insert_position(db_path, "TSLA", 5, 200.0, 0.0, status="open")
        await _insert_annotation(db_path, "TSLA", "Speculative entry", "entry_timing")
        analytics = JournalAnalytics(db_path)
        result = await analytics.get_lesson_tag_stats()
        assert result == []
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_single_tag_all_wins() -> None:
    """Single tag with all winning trades gives 100% win rate."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        await _setup_db(db_path)
        await _insert_position(db_path, "AAPL", 10, 150.0, 200.0)
        await _insert_position(db_path, "MSFT", 10, 300.0, 150.0)
        await _insert_annotation(db_path, "AAPL", "Good entry", "entry_timing")
        await _insert_annotation(db_path, "MSFT", "Strong thesis", "entry_timing")

        analytics = JournalAnalytics(db_path)
        result = await analytics.get_lesson_tag_stats()

        assert len(result) == 1
        stat = result[0]
        assert stat["tag"] == "entry_timing"
        assert stat["count"] == 2
        assert stat["win_count"] == 2
        assert stat["loss_count"] == 0
        assert stat["win_rate"] == 100.0
        assert stat["avg_return_pct"] > 0
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_single_tag_all_losses() -> None:
    """Single tag with all losing trades gives 0% win rate."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        await _setup_db(db_path)
        await _insert_position(db_path, "AAPL", 10, 150.0, -100.0)
        await _insert_position(db_path, "TSLA", 5, 200.0, -50.0)
        await _insert_annotation(db_path, "AAPL", "Bad timing", "emotional")
        await _insert_annotation(db_path, "TSLA", "FOMO", "emotional")

        analytics = JournalAnalytics(db_path)
        result = await analytics.get_lesson_tag_stats()

        assert len(result) == 1
        stat = result[0]
        assert stat["tag"] == "emotional"
        assert stat["count"] == 2
        assert stat["win_count"] == 0
        assert stat["loss_count"] == 2
        assert stat["win_rate"] == 0.0
        assert stat["avg_return_pct"] < 0
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_mixed_wins_and_losses() -> None:
    """Multiple tags with mixed outcomes produce correct per-tag stats."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        await _setup_db(db_path)
        # Two winning positions
        await _insert_position(db_path, "AAPL", 10, 150.0, 200.0)  # +13.3%
        await _insert_position(db_path, "MSFT", 10, 300.0, 100.0)  # +3.3%
        # One losing position
        await _insert_position(db_path, "TSLA", 5, 200.0, -100.0)  # -10%

        # entry_timing: 1 win (AAPL), 1 loss (TSLA) -> 50%
        await _insert_annotation(db_path, "AAPL", "Good entry", "entry_timing")
        await _insert_annotation(db_path, "TSLA", "Bad entry", "entry_timing")

        # thesis_quality: 1 win (MSFT) -> 100%
        await _insert_annotation(db_path, "MSFT", "Strong thesis", "thesis_quality")

        analytics = JournalAnalytics(db_path)
        result = await analytics.get_lesson_tag_stats()

        # Results are ordered by count DESC
        assert len(result) == 2
        by_tag = {r["tag"]: r for r in result}

        entry = by_tag["entry_timing"]
        assert entry["count"] == 2
        assert entry["win_count"] == 1
        assert entry["loss_count"] == 1
        assert entry["win_rate"] == 50.0

        thesis = by_tag["thesis_quality"]
        assert thesis["count"] == 1
        assert thesis["win_count"] == 1
        assert thesis["loss_count"] == 0
        assert thesis["win_rate"] == 100.0
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_avg_return_pct_calculation() -> None:
    """avg_return_pct is calculated as realized_pnl / cost_basis * 100."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        await _setup_db(db_path)
        # AAPL: 10 shares @ $100, realized_pnl = $200 -> return = 200/1000*100 = 20%
        await _insert_position(db_path, "AAPL", 10, 100.0, 200.0)
        # MSFT: 10 shares @ $200, realized_pnl = -100 -> return = -100/2000*100 = -5%
        await _insert_position(db_path, "MSFT", 10, 200.0, -100.0)

        await _insert_annotation(db_path, "AAPL", "Note 1", "risk_management")
        await _insert_annotation(db_path, "MSFT", "Note 2", "risk_management")

        analytics = JournalAnalytics(db_path)
        result = await analytics.get_lesson_tag_stats()

        assert len(result) == 1
        stat = result[0]
        # avg of 20% and -5% = 7.5%
        assert abs(stat["avg_return_pct"] - 7.5) < 0.1
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_multiple_annotations_on_same_position() -> None:
    """Multiple annotations on the same closed position are counted separately."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        await _setup_db(db_path)
        await _insert_position(db_path, "AAPL", 10, 150.0, 200.0)
        await _insert_annotation(db_path, "AAPL", "Good entry", "entry_timing")
        await _insert_annotation(db_path, "AAPL", "Good exit", "exit_timing")

        analytics = JournalAnalytics(db_path)
        result = await analytics.get_lesson_tag_stats()

        assert len(result) == 2
        by_tag = {r["tag"]: r for r in result}
        assert by_tag["entry_timing"]["count"] == 1
        assert by_tag["exit_timing"]["count"] == 1
        # Both are wins since AAPL had positive realized_pnl
        assert by_tag["entry_timing"]["win_count"] == 1
        assert by_tag["exit_timing"]["win_count"] == 1
    finally:
        os.unlink(db_path)
