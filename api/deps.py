"""Shared FastAPI dependencies and utilities."""
from __future__ import annotations

from fastapi import Request

# Crypto auto-detect (same logic as cli/analyze_cli.py)
_CRYPTO_TICKERS = {"BTC", "ETH", "BTC-USD", "ETH-USD"}
_CRYPTO_YF_MAP = {"BTC": "BTC-USD", "ETH": "ETH-USD"}


def get_db_path(request: Request) -> str:
    """Extract db_path from app state (set in create_app)."""
    return request.app.state.db_path


def resolve_asset_type(ticker: str, asset_type: str = "stock") -> str:
    """Auto-detect crypto tickers and return corrected asset_type."""
    upper = ticker.upper()
    if asset_type == "stock" and upper in _CRYPTO_TICKERS:
        if upper in ("BTC", "BTC-USD"):
            return "btc"
        return "eth"
    return asset_type


def map_ticker(ticker: str, asset_type: str) -> str:
    """Map bare crypto tickers to yfinance format."""
    upper = ticker.upper()
    if asset_type in ("btc", "eth"):
        return _CRYPTO_YF_MAP.get(upper, upper)
    return upper
