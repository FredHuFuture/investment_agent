"""FastAPI application factory."""
from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.models import ErrorDetail, ErrorResponse
from db.database import DEFAULT_DB_PATH, init_db

# Windows: aiodns (used by aiohttp) requires SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    await init_db(app.state.db_path)
    yield


def create_app(db_path: str = str(DEFAULT_DB_PATH)) -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Investment Agent API",
        version="0.1.0",
        description="REST API for investment analysis, portfolio management, and backtesting.",
        lifespan=lifespan,
    )
    app.state.db_path = db_path

    # CORS for future React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Exception handlers --------------------------------------------------

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error=ErrorDetail(code="VALIDATION_ERROR", message=str(exc))
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(code="INTERNAL_ERROR", message=str(exc))
            ).model_dump(),
        )

    # -- Health endpoint (inline) ---------------------------------------------

    @app.get("/health", tags=["system"])
    async def health():
        return {"data": {"status": "ok", "db_path": app.state.db_path}, "warnings": []}

    # -- Register routers -----------------------------------------------------

    from api.routes.analyze import router as analyze_router
    from api.routes.alerts import router as alerts_router
    from api.routes.analytics import router as analytics_router
    from api.routes.backtest import router as backtest_router
    from api.routes.daemon import router as daemon_router
    from api.routes.export import router as export_router
    from api.routes.portfolio import router as portfolio_router
    from api.routes.profiles import router as profiles_router
    from api.routes.signals import router as signals_router
    from api.routes.summary import router as summary_router
    from api.routes.watchlist import router as watchlist_router
    from api.routes.regime import router as regime_router
    from api.routes.weights import router as weights_router
    from api.routes.journal import router as journal_router

    app.include_router(analyze_router, prefix="/analyze", tags=["analysis"])
    app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
    app.include_router(portfolio_router, prefix="/portfolio", tags=["portfolio"])
    app.include_router(profiles_router, prefix="/portfolios", tags=["portfolios"])
    app.include_router(alerts_router, tags=["monitoring"])
    app.include_router(backtest_router, prefix="/backtest", tags=["backtesting"])
    app.include_router(signals_router, prefix="/signals", tags=["signals"])
    app.include_router(daemon_router, prefix="/daemon", tags=["daemon"])
    app.include_router(summary_router, prefix="/summary", tags=["summary"])
    app.include_router(weights_router, tags=["weights"])
    app.include_router(export_router, prefix="/api/export", tags=["export"])
    app.include_router(watchlist_router, prefix="/watchlist", tags=["watchlist"])
    app.include_router(regime_router, prefix="/regime", tags=["regime"])
    app.include_router(journal_router, prefix="/journal", tags=["journal"])

    # Risk router (Agent B — Sprint 29 Task 3)
    try:
        from api.routes.risk import router as risk_router
        app.include_router(risk_router, prefix="/risk", tags=["risk"])
    except ImportError:
        pass  # risk route not yet implemented

    return app


# Default app instance for `uvicorn api.app:app`
app = create_app()
