"""Analysis endpoint."""
from __future__ import annotations

import logging
import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.deps import get_db_path, map_ticker, resolve_asset_type
from data_providers.factory import get_provider
from data_providers.web_news_provider import WebNewsProvider
from agents.sentiment import SentimentAgent, parse_sentiment_response
from engine.pipeline import AnalysisPipeline
from engine.aggregator import SignalAggregator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{ticker}/catalysts")
async def get_catalysts(
    ticker: str,
    asset_type: Literal["stock", "btc", "eth"] = Query("stock"),
):
    """Fetch news headlines and sentiment analysis for a ticker."""
    asset_type = resolve_asset_type(ticker, asset_type)
    yf_ticker = map_ticker(ticker, asset_type)
    warnings: list[str] = []

    # 1. Fetch headlines from WebNewsProvider
    headlines_data: list[dict[str, Any]] = []
    news_provider = WebNewsProvider()
    try:
        raw_headlines = await news_provider.get_headlines(yf_ticker, max_results=10)
        headlines_data = [
            {
                "title": h.title,
                "source": h.source,
                "published_at": h.published_at,
                "url": h.url,
            }
            for h in raw_headlines
        ]
    except Exception as exc:
        logger.warning("WebNewsProvider failed for %s: %s", yf_ticker, exc)
        warnings.append(f"News fetch failed: {exc}")
        raw_headlines = []

    # 2. Optionally run SentimentAgent analysis if ANTHROPIC_API_KEY is set
    sentiment_data: dict[str, Any] | None = None
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and raw_headlines:
        try:
            from anthropic import AsyncAnthropic

            _MODEL = "claude-sonnet-4-20250514"
            _SYSTEM_PROMPT = (
                "You are a financial news sentiment analysis engine. "
                "Analyse ONLY the sentiment conveyed by the headlines. "
                "Return a single valid JSON object with fields: "
                '"signal" (BUY/HOLD/SELL), "confidence" (0-100), '
                '"sentiment_score" (-1.0 to 1.0), '
                '"catalysts" (list of short strings), '
                '"reasoning" (1-3 sentences). '
                "Return ONLY the JSON object."
            )

            lines: list[str] = [
                f"Ticker: {yf_ticker}",
                f"Number of headlines: {len(raw_headlines)}",
                "",
                "Headlines:",
            ]
            for i, h in enumerate(raw_headlines, 1):
                entry = f"{i}. [{h.source}] {h.title} (published {h.published_at})"
                if h.snippet:
                    entry += f"\n   Snippet: {h.snippet}"
                lines.append(entry)
            lines.append("")
            lines.append(
                "Analyse the sentiment of these headlines and return your JSON assessment."
            )
            user_message = "\n".join(lines)

            client = AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                model=_MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw_text = response.content[0].text
            parsed = parse_sentiment_response(raw_text)
            sentiment_data = {
                "signal": parsed["signal"],
                "confidence": parsed["confidence"],
                "sentiment_score": parsed["sentiment_score"],
                "catalysts": parsed["catalysts"],
                "reasoning": parsed["reasoning"],
            }
        except ImportError:
            warnings.append("anthropic package not installed — sentiment analysis unavailable.")
        except Exception as exc:
            logger.warning("Sentiment analysis failed for %s: %s", yf_ticker, exc)
            warnings.append(f"Sentiment analysis failed: {exc}")
    elif not api_key:
        # No API key — skip sentiment silently (null in response)
        pass

    return {
        "data": {
            "headlines": headlines_data,
            "sentiment": sentiment_data,
        },
        "warnings": warnings,
    }


@router.get("/{ticker}/price-history")
async def get_price_history(
    ticker: str,
    asset_type: Literal["stock", "btc", "eth"] = Query("stock"),
    period: str = Query("1y"),
):
    """Fetch price history for chart display."""
    asset_type = resolve_asset_type(ticker, asset_type)
    yf_ticker = map_ticker(ticker, asset_type)

    provider = get_provider(asset_type)
    try:
        df = await provider.get_price_history(yf_ticker, period=period)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {"code": "UPSTREAM_ERROR", "message": str(exc), "detail": None}
            },
        )

    # Convert to OHLCV JSON: [{date, open, high, low, close, volume}, ...]
    points = []
    for idx, row in df.iterrows():
        points.append({
            "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]) if "Volume" in row else 0,
        })
    return {"data": points, "warnings": []}


@router.get("/{ticker}")
async def analyze_ticker(
    ticker: str,
    asset_type: Literal["stock", "btc", "eth"] = Query("stock"),
    adaptive_weights: bool = Query(False),
    db_path: str = Depends(get_db_path),
):
    """Run multi-agent analysis for a single ticker."""
    asset_type = resolve_asset_type(ticker, asset_type)
    yf_ticker = map_ticker(ticker, asset_type)

    pipeline = AnalysisPipeline(db_path=db_path, use_adaptive_weights=adaptive_weights)
    try:
        result = await pipeline.analyze_ticker(yf_ticker, asset_type)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {"code": "UPSTREAM_ERROR", "message": str(exc), "detail": None}
            },
        )
    return {"data": result.to_dict(), "warnings": result.warnings}


class CustomWeightsRequest(BaseModel):
    ticker: str
    asset_type: str = "stock"
    weights: dict[str, float]


@router.post("/{ticker}")
async def analyze_ticker_custom(
    ticker: str,
    body: CustomWeightsRequest,
    db_path: str = Depends(get_db_path),
):
    """Run analysis with user-specified agent weights."""
    asset_type = resolve_asset_type(ticker, body.asset_type)
    yf_ticker = map_ticker(ticker, asset_type)

    pipeline = AnalysisPipeline(db_path=db_path, use_adaptive_weights=False)

    custom_weights = dict(SignalAggregator.DEFAULT_WEIGHTS)
    custom_weights[asset_type] = dict(body.weights)

    try:
        result = await pipeline.analyze_ticker_custom(yf_ticker, asset_type, custom_weights)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={
                "error": {"code": "UPSTREAM_ERROR", "message": str(exc), "detail": None}
            },
        )
    return {"data": result.to_dict(), "warnings": result.warnings}
