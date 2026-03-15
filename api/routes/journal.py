"""Trade journal annotation endpoints."""
from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_db_path
from engine.journal_analytics import JournalAnalytics

router = APIRouter()

_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS trade_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_ticker TEXT NOT NULL,
    annotation_text TEXT NOT NULL,
    lesson_tag TEXT,
    created_at TEXT DEFAULT (datetime('now'))
)
"""


class CreateAnnotationRequest(BaseModel):
    annotation_text: str
    lesson_tag: str | None = None


async def _ensure_table(db_path: str) -> None:
    """Create the trade_annotations table if it does not exist."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(_CREATE_TABLE_SQL)
        await conn.commit()


@router.get("/annotations/{ticker}")
async def get_annotations(
    ticker: str,
    db_path: str = Depends(get_db_path),
):
    """Fetch all annotations for a closed position ticker."""
    await _ensure_table(db_path)
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, position_ticker, annotation_text, lesson_tag, created_at "
            "FROM trade_annotations WHERE position_ticker = ? ORDER BY created_at DESC",
            (ticker.upper(),),
        )
        rows = await cursor.fetchall()

    data = [
        {
            "id": row["id"],
            "position_ticker": row["position_ticker"],
            "annotation_text": row["annotation_text"],
            "lesson_tag": row["lesson_tag"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"data": data, "warnings": []}


@router.post("/annotations/{ticker}")
async def create_annotation(
    ticker: str,
    body: CreateAnnotationRequest,
    db_path: str = Depends(get_db_path),
):
    """Create a new annotation for a closed position."""
    if not body.annotation_text.strip():
        raise HTTPException(status_code=400, detail="Annotation text cannot be empty")

    await _ensure_table(db_path)
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO trade_annotations (position_ticker, annotation_text, lesson_tag) "
            "VALUES (?, ?, ?)",
            (ticker.upper(), body.annotation_text.strip(), body.lesson_tag),
        )
        await conn.commit()
        row_id = cursor.lastrowid

        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, position_ticker, annotation_text, lesson_tag, created_at "
            "FROM trade_annotations WHERE id = ?",
            (row_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=500, detail="Failed to create annotation")

    data = {
        "id": row["id"],
        "position_ticker": row["position_ticker"],
        "annotation_text": row["annotation_text"],
        "lesson_tag": row["lesson_tag"],
        "created_at": row["created_at"],
    }
    return {"data": data, "warnings": []}


@router.get("/lesson-stats")
async def lesson_stats(db_path: str = Depends(get_db_path)):
    """Compute win-rate-by-tag analytics for lesson annotations."""
    analytics = JournalAnalytics(db_path)
    data = await analytics.get_lesson_tag_stats()
    return {"data": data, "warnings": []}
