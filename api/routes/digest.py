"""Weekly digest endpoint (LIVE-04 — Phase 7).

POST /digest/weekly returns a Markdown body assembled by
engine.digest.render_weekly_digest. The endpoint is fired both by users
on demand and by the Sunday 18:00 APScheduler job (which calls render
directly + dispatches via email/Telegram).

PII discipline is enforced at the renderer layer — no dollar amounts or
thesis text appear in the returned Markdown (T-07-02-02).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from api.deps import get_db_path

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/weekly", response_class=PlainTextResponse)
async def post_weekly_digest(
    db_path: str = Depends(get_db_path),
) -> PlainTextResponse:
    """Render and return the weekly Markdown digest.

    Returns text/markdown so curl/email clients display the content
    directly. PII-clamped at the renderer (no dollar amounts, no thesis
    text) — see engine.digest module docstring.

    Dispatch (email/Telegram) is handled by the daemon scheduler job
    at Sunday 18:00 US/Eastern — this endpoint is for on-demand preview
    and integration testing.
    """
    from engine.digest import render_weekly_digest  # noqa: PLC0415

    body = await render_weekly_digest(db_path)
    _logger.info("Digest rendered on-demand: %d chars", len(body))
    return PlainTextResponse(content=body, media_type="text/markdown")
