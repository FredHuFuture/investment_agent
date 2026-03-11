"""Adaptive weights endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_db_path
from engine.aggregator import SignalAggregator
from engine.weight_adapter import WeightAdapter

router = APIRouter()


@router.get("/weights")
async def get_weights(db_path: str = Depends(get_db_path)):
    """Return current adaptive weights (or defaults if none saved)."""
    adapter = WeightAdapter(db_path=db_path)
    weights = await adapter.load_weights()
    if weights is None:
        return {
            "data": {
                "weights": dict(SignalAggregator.DEFAULT_WEIGHTS),
                "buy_threshold": 0.30,
                "sell_threshold": -0.30,
                "source": "default",
                "sample_size": 0,
            },
            "warnings": [],
        }
    return {"data": weights.to_dict(), "warnings": []}
