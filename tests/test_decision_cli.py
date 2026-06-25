# tests/test_decision_cli.py
from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agents.models import Regime, Signal
from db.database import init_db
from engine.aggregator import AggregatedSignal


def _signal() -> AggregatedSignal:
    return AggregatedSignal(
        ticker="AAPL", asset_type="stock", final_signal=Signal.BUY, final_confidence=70.0,
        regime=Regime.RISK_ON, agent_signals=[], reasoning="cli test",
    )


def _ns(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


@pytest.fixture
async def db_file(tmp_path: Path) -> str:
    path = str(tmp_path / "cli.db")
    await init_db(path)
    return path


async def test_propose_then_lifecycle(db_file: str, capsys) -> None:
    from cli import decision_cli

    mock_pipeline = AsyncMock()
    mock_pipeline.analyze_ticker = AsyncMock(return_value=_signal())
    with patch("cli.decision_cli.AnalysisPipeline", return_value=mock_pipeline):
        await decision_cli._handle_propose(
            _ns(db_path=db_file, ticker="AAPL", qty=None, asset_type="stock")
        )
    out = capsys.readouterr().out
    assert "pending" in out.lower()

    # Approve id 1
    await decision_cli._handle_approve(_ns(db_path=db_file, id=1, by="you"))
    # Execute id 1 with a stubbed paper price
    async def fake_price(ticker, asset_type):
        return 150.0
    with patch("cli.decision_cli.PaperExecutionAdapter",
               return_value=__import__("execution.paper", fromlist=["PaperExecutionAdapter"])
               .PaperExecutionAdapter(price_fetch_fn=fake_price)):
        await decision_cli._handle_execute(_ns(db_path=db_file, id=1))
    out = capsys.readouterr().out
    assert "executed" in out.lower()

    # Verify chain
    await decision_cli._handle_verify(_ns(db_path=db_file))
    out = capsys.readouterr().out
    assert "ok" in out.lower() or "valid" in out.lower()


async def test_execute_without_approve_exits_nonzero(db_file: str) -> None:
    from cli import decision_cli

    mock_pipeline = AsyncMock()
    mock_pipeline.analyze_ticker = AsyncMock(return_value=_signal())
    with patch("cli.decision_cli.AnalysisPipeline", return_value=mock_pipeline):
        await decision_cli._handle_propose(
            _ns(db_path=db_file, ticker="AAPL", qty=None, asset_type="stock")
        )
    with pytest.raises(SystemExit) as ei:
        await decision_cli._handle_execute(_ns(db_path=db_file, id=1))
    assert ei.value.code == 1
