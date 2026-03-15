"""Notification configuration endpoints."""
from __future__ import annotations

from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_db_path

router = APIRouter()

DEFAULTS: dict[str, str] = {
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_enabled": "false",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_enabled": "false",
    "notify_critical": "true",
    "notify_high": "true",
    "notify_warning": "false",
    "notify_info": "false",
}

BOOL_FIELDS = {
    "smtp_enabled",
    "telegram_enabled",
    "notify_critical",
    "notify_high",
    "notify_warning",
    "notify_info",
}

INT_FIELDS = {"smtp_port"}


class NotificationConfigBody(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_enabled: Optional[bool] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    notify_critical: Optional[bool] = None
    notify_high: Optional[bool] = None
    notify_warning: Optional[bool] = None
    notify_info: Optional[bool] = None


def _parse_value(field: str, raw: str):
    """Convert a stored string value to the appropriate Python type."""
    if field in BOOL_FIELDS:
        return raw.lower() in ("true", "1", "yes")
    if field in INT_FIELDS:
        try:
            return int(raw)
        except ValueError:
            return int(DEFAULTS[field])
    return raw


def _serialize_value(field: str, value) -> str:
    """Convert a Python value to a string for storage."""
    if field in BOOL_FIELDS:
        return "true" if value else "false"
    return str(value)


async def _read_full_config(db: aiosqlite.Connection) -> dict:
    """Read all notif_ keys from portfolio_meta, filling defaults."""
    config = {}
    for field, default_val in DEFAULTS.items():
        key = f"notif_{field}"
        cur = await db.execute(
            "SELECT value FROM portfolio_meta WHERE key = ?", (key,)
        )
        row = await cur.fetchone()
        raw = row[0] if row else default_val
        config[field] = _parse_value(field, raw)
    return config


@router.get("/config")
async def get_notification_config(db_path: str = Depends(get_db_path)):
    """Return the full notification configuration with defaults for missing keys."""
    async with aiosqlite.connect(db_path) as db:
        config = await _read_full_config(db)
    return {"data": config, "warnings": []}


@router.put("/config")
async def save_notification_config(
    body: NotificationConfigBody,
    db_path: str = Depends(get_db_path),
):
    """Upsert provided notification config fields and return the full config."""
    updates = body.model_dump(exclude_none=True)

    async with aiosqlite.connect(db_path) as db:
        for field, value in updates.items():
            key = f"notif_{field}"
            str_value = _serialize_value(field, value)
            await db.execute(
                """
                INSERT INTO portfolio_meta (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key)
                DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, str_value),
            )
        await db.commit()
        config = await _read_full_config(db)

    return {"data": config, "warnings": []}
