"""Portfolio profiles endpoints (Sprint 13.4: Multi-Portfolio Support)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.deps import get_db_path
from portfolio.profiles import PortfolioProfileManager

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    initial_cash: float = Field(default=0, ge=0)


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_portfolios(db_path: str = Depends(get_db_path)):
    """List all portfolio profiles."""
    mgr = PortfolioProfileManager(db_path)
    profiles = await mgr.list_profiles()
    return {"data": profiles, "warnings": []}


@router.post("")
async def create_portfolio(body: CreateProfileRequest, db_path: str = Depends(get_db_path)):
    """Create a new portfolio profile."""
    mgr = PortfolioProfileManager(db_path)
    profile = await mgr.create_profile(
        name=body.name,
        description=body.description,
        initial_cash=body.initial_cash,
    )
    return {"data": profile, "warnings": []}


@router.get("/{profile_id}")
async def get_portfolio_profile(profile_id: int, db_path: str = Depends(get_db_path)):
    """Get a single portfolio profile by id."""
    mgr = PortfolioProfileManager(db_path)
    profile = await mgr.get_profile(profile_id)
    if profile is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Portfolio profile {profile_id} not found.",
                    "detail": None,
                }
            },
        )
    return {"data": profile, "warnings": []}


@router.put("/{profile_id}")
async def update_portfolio_profile(
    profile_id: int,
    body: UpdateProfileRequest,
    db_path: str = Depends(get_db_path),
):
    """Update name and/or description of a portfolio profile."""
    mgr = PortfolioProfileManager(db_path)
    updated = await mgr.update_profile(
        profile_id=profile_id,
        name=body.name,
        description=body.description,
    )
    if not updated:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Portfolio profile {profile_id} not found.",
                    "detail": None,
                }
            },
        )
    profile = await mgr.get_profile(profile_id)
    return {"data": profile, "warnings": []}


@router.delete("/{profile_id}")
async def delete_portfolio_profile(profile_id: int, db_path: str = Depends(get_db_path)):
    """Delete a portfolio profile (only if it has no positions)."""
    mgr = PortfolioProfileManager(db_path)
    deleted = await mgr.delete_profile(profile_id)
    if not deleted:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Portfolio profile {profile_id} not found.",
                    "detail": None,
                }
            },
        )
    return {"data": {"deleted": True}, "warnings": []}


@router.post("/{profile_id}/set-default")
async def set_default_portfolio(profile_id: int, db_path: str = Depends(get_db_path)):
    """Set a portfolio profile as the default."""
    mgr = PortfolioProfileManager(db_path)
    success = await mgr.set_default(profile_id)
    if not success:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Portfolio profile {profile_id} not found.",
                    "detail": None,
                }
            },
        )
    return {"data": {"default_profile_id": profile_id}, "warnings": []}
