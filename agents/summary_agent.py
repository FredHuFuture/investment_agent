"""Weekly portfolio summary agent using Claude API.

Generates a natural language review of each position's thesis against
recent market reality.  ONE agent, ONE prompt, ONE response.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # type: ignore[assignment,misc]

from portfolio.manager import PortfolioManager

logger = logging.getLogger(__name__)

# Claude Sonnet pricing (USD per token)
_INPUT_PRICE_PER_TOKEN = 3.0 / 1_000_000   # $3 / 1M input tokens
_OUTPUT_PRICE_PER_TOKEN = 15.0 / 1_000_000  # $15 / 1M output tokens

_SYSTEM_PROMPT = """\
You are an investment analysis assistant. Review the portfolio below and write a concise weekly summary.

For each position:
1. If the user recorded a thesis, evaluate whether recent price action supports or contradicts it
2. Flag any positions where hold time exceeds the planned duration
3. Flag positions approaching stop loss or significantly exceeding target
4. Note any positions where the latest agent signal disagrees with the current holding

Keep it conversational but data-driven. Use specific numbers. 3-5 sentences per position.
End with a 1-2 sentence overall portfolio assessment.

IMPORTANT: You are NOT giving investment advice. You are helping the user evaluate their OWN thesis.
Do NOT recommend specific actions. Instead, flag observations and let the user decide.
"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PositionContext:
    """Context for a single portfolio position sent to Claude."""

    ticker: str
    asset_type: str
    quantity: float
    avg_cost: float
    current_price: float
    unrealized_pnl_pct: float
    holding_days: int
    # Thesis fields (may be None)
    thesis_text: str | None = None
    expected_return_pct: float | None = None
    expected_hold_days: int | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    # Latest agent signal
    latest_signal: str | None = None
    latest_confidence: float | None = None
    # Price action this week
    week_return_pct: float | None = None


@dataclass
class PortfolioContext:
    """Full portfolio context sent to Claude."""

    positions: list[PositionContext]
    total_value: float
    cash_pct: float
    period: str  # e.g. "2026-03-04 to 2026-03-11"


@dataclass
class SummaryResult:
    """Result from Claude summary generation."""

    summary_text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    positions_covered: list[str]


# ---------------------------------------------------------------------------
# SummaryAgent
# ---------------------------------------------------------------------------

class SummaryAgent:
    """Generates weekly portfolio summaries using Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

    @classmethod
    async def build_context(cls, db_path: str) -> PortfolioContext:
        """Gather all data needed for the summary from existing DB."""
        mgr = PortfolioManager(db_path)
        portfolio = await mgr.load_portfolio()

        today = date.today()
        week_ago = today - timedelta(days=7)
        period = f"{week_ago.isoformat()} to {today.isoformat()}"

        total_value = portfolio.total_value
        cash_pct = portfolio.cash_pct

        position_contexts: list[PositionContext] = []

        async with aiosqlite.connect(db_path) as conn:
            for pos in portfolio.positions:
                # Fetch latest signal from signal_history
                latest_signal: str | None = None
                latest_confidence: float | None = None
                sig_row = await (
                    await conn.execute(
                        """
                        SELECT final_signal, final_confidence
                        FROM signal_history
                        WHERE ticker = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (pos.ticker,),
                    )
                ).fetchone()
                if sig_row is not None:
                    latest_signal = str(sig_row[0])
                    latest_confidence = float(sig_row[1])

                # Fetch week return via yfinance (best-effort)
                week_return_pct: float | None = None
                current_price = pos.current_price
                try:
                    import yfinance as yf

                    ticker_yf = pos.ticker
                    if pos.asset_type in ("btc", "eth"):
                        mapping = {"BTC": "BTC-USD", "ETH": "ETH-USD"}
                        ticker_yf = mapping.get(pos.ticker.upper(), pos.ticker)

                    data = yf.download(
                        ticker_yf,
                        period="10d",
                        progress=False,
                        auto_adjust=True,
                    )
                    if data is not None and len(data) >= 2:
                        # Handle MultiIndex columns
                        close_col = data["Close"]
                        if hasattr(close_col, "columns"):
                            close_col = close_col.iloc[:, 0]
                        latest_close = float(close_col.iloc[-1])
                        oldest_close = float(close_col.iloc[0])
                        if oldest_close > 0:
                            week_return_pct = (latest_close - oldest_close) / oldest_close
                        if current_price == 0.0:
                            current_price = latest_close
                except Exception:
                    logger.debug("Failed to fetch week return for %s", pos.ticker)

                # Get thesis data
                thesis = await mgr.get_thesis(pos.ticker)

                pctx = PositionContext(
                    ticker=pos.ticker,
                    asset_type=pos.asset_type,
                    quantity=pos.quantity,
                    avg_cost=pos.avg_cost,
                    current_price=current_price,
                    unrealized_pnl_pct=(
                        (current_price - pos.avg_cost) / pos.avg_cost
                        if pos.avg_cost > 0 and current_price > 0
                        else 0.0
                    ),
                    holding_days=pos.holding_days,
                    thesis_text=thesis.get("thesis_text") if thesis else pos.thesis_text,
                    expected_return_pct=(
                        thesis.get("expected_return_pct") if thesis else pos.expected_return_pct
                    ),
                    expected_hold_days=(
                        thesis.get("expected_hold_days") if thesis else pos.expected_hold_days
                    ),
                    target_price=(
                        thesis.get("expected_target_price") if thesis else pos.target_price
                    ),
                    stop_loss=(
                        thesis.get("expected_stop_loss") if thesis else pos.stop_loss
                    ),
                    latest_signal=latest_signal,
                    latest_confidence=latest_confidence,
                    week_return_pct=week_return_pct,
                )
                position_contexts.append(pctx)

        return PortfolioContext(
            positions=position_contexts,
            total_value=total_value,
            cash_pct=cash_pct,
            period=period,
        )

    async def generate_summary(self, context: PortfolioContext) -> SummaryResult:
        """Generate a natural language portfolio review via Claude API."""
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Set the environment variable or pass api_key to SummaryAgent."
            )

        user_message = self._build_user_message(context)

        client = AsyncAnthropic(api_key=self.api_key)
        response = await client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        summary_text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost_usd = self._compute_cost(input_tokens, output_tokens)

        # Append disclaimer
        summary_text = summary_text.rstrip() + "\n\n---\n*This is not investment advice.*"

        positions_covered = [p.ticker for p in context.positions]

        return SummaryResult(
            summary_text=summary_text,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost_usd, 6),
            positions_covered=positions_covered,
        )

    @staticmethod
    def _compute_cost(input_tokens: int, output_tokens: int) -> float:
        """Compute USD cost from token counts using Sonnet pricing."""
        return (
            input_tokens * _INPUT_PRICE_PER_TOKEN
            + output_tokens * _OUTPUT_PRICE_PER_TOKEN
        )

    @staticmethod
    def _build_user_message(context: PortfolioContext) -> str:
        """Build the user message with portfolio data for Claude."""
        lines: list[str] = []
        lines.append(f"## Portfolio Review Period: {context.period}")
        lines.append(f"Total Value: ${context.total_value:,.2f}")
        lines.append(f"Cash: {context.cash_pct:.1%}")
        lines.append("")

        for p in context.positions:
            lines.append(f"### {p.ticker} ({p.asset_type})")
            lines.append(f"- Quantity: {p.quantity}")
            lines.append(f"- Avg Cost: ${p.avg_cost:,.2f}")
            lines.append(f"- Current Price: ${p.current_price:,.2f}")
            lines.append(f"- Unrealized P&L: {p.unrealized_pnl_pct:+.1%}")
            lines.append(f"- Holding Days: {p.holding_days}")

            if p.week_return_pct is not None:
                lines.append(f"- Week Return: {p.week_return_pct:+.1%}")

            if p.thesis_text:
                lines.append(f"- Thesis: {p.thesis_text}")
            if p.expected_return_pct is not None:
                lines.append(f"- Expected Return: {p.expected_return_pct:+.1%}")
            if p.expected_hold_days is not None:
                lines.append(f"- Expected Hold: {p.expected_hold_days} days")
            if p.target_price is not None:
                lines.append(f"- Target Price: ${p.target_price:,.2f}")
            if p.stop_loss is not None:
                lines.append(f"- Stop Loss: ${p.stop_loss:,.2f}")

            if p.latest_signal:
                conf_str = f" ({p.latest_confidence:.0f})" if p.latest_confidence is not None else ""
                lines.append(f"- Latest Signal: {p.latest_signal}{conf_str}")

            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# DB persistence helper
# ---------------------------------------------------------------------------

async def save_summary(db_path: str, result: SummaryResult) -> int:
    """Save a SummaryResult to the portfolio_summaries table. Returns row id."""
    async with aiosqlite.connect(db_path) as conn:
        now = datetime.now(timezone.utc).isoformat()
        cursor = await conn.execute(
            """
            INSERT INTO portfolio_summaries
                (summary_text, generated_at, model, input_tokens, output_tokens,
                 cost_usd, positions_covered)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.summary_text,
                now,
                result.model,
                result.input_tokens,
                result.output_tokens,
                result.cost_usd,
                json.dumps(result.positions_covered),
            ),
        )
        await conn.commit()
        return int(cursor.lastrowid)


async def get_latest_summary(db_path: str) -> dict[str, Any] | None:
    """Return the most recent summary from DB, or None."""
    async with aiosqlite.connect(db_path) as conn:
        row = await (
            await conn.execute(
                """
                SELECT id, summary_text, generated_at, model,
                       input_tokens, output_tokens, cost_usd, positions_covered
                FROM portfolio_summaries
                ORDER BY generated_at DESC
                LIMIT 1
                """
            )
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "summary_text": row[1],
            "generated_at": row[2],
            "model": row[3],
            "input_tokens": row[4],
            "output_tokens": row[5],
            "cost_usd": row[6],
            "positions_covered": json.loads(row[7]) if row[7] else [],
        }
