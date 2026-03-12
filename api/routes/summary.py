"""Portfolio summary endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.deps import get_db_path
from api.models import APIResponse, ErrorDetail, ErrorResponse, SummaryResponse
from agents.summary_agent import SummaryAgent, get_latest_summary, save_summary

router = APIRouter()


@router.post("/generate")
async def generate_summary(db_path: str = Depends(get_db_path)):
    """Generate a new portfolio summary using Claude API.

    Requires ANTHROPIC_API_KEY environment variable.
    Returns 503 if the key is not set.
    """
    agent = SummaryAgent()
    if not agent.api_key:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="API_KEY_MISSING",
                    message=(
                        "ANTHROPIC_API_KEY is not set. "
                        "Set the environment variable to enable AI summaries."
                    ),
                )
            ).model_dump(),
        )

    try:
        context = await SummaryAgent.build_context(db_path)
        result = await agent.generate_summary(context)
        await save_summary(db_path, result)

        generated_at = datetime.now(timezone.utc).isoformat()
        return APIResponse(
            data=SummaryResponse(
                summary_text=result.summary_text,
                generated_at=generated_at,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=result.cost_usd,
                positions_covered=result.positions_covered,
            ).model_dump(),
            warnings=[],
        ).model_dump()
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="SUMMARY_GENERATION_FAILED",
                    message=f"Summary generation failed: {exc}",
                )
            ).model_dump(),
        )


@router.get("/latest")
async def latest_summary(db_path: str = Depends(get_db_path)):
    """Return the most recent saved summary.

    Returns 404 if no summaries exist yet.
    """
    summary = await get_latest_summary(db_path)
    if summary is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="NO_SUMMARY",
                    message="No portfolio summary has been generated yet.",
                )
            ).model_dump(),
        )

    return APIResponse(
        data=SummaryResponse(
            summary_text=summary["summary_text"],
            generated_at=summary["generated_at"],
            model=summary["model"],
            input_tokens=summary["input_tokens"],
            output_tokens=summary["output_tokens"],
            cost_usd=summary["cost_usd"],
            positions_covered=summary["positions_covered"],
        ).model_dump(),
        warnings=[],
    ).model_dump()
