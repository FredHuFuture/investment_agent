"""SIG-01 CVaR correctness + matplotlib-leak regression tests.

Tests:
  A  test_cvar_matches_quantstats_reference
  B  test_cvar_not_gaussian_on_fat_tail
  C  test_cvar_99_greater_than_cvar_95
  D  test_cvar_none_when_insufficient_data
  E  test_matplotlib_not_imported_on_engine_analytics_import
  F  test_portfolio_var_method_field_present
"""
from __future__ import annotations

import os
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite
import pandas as pd
import quantstats.stats as qs_stats

from db.database import init_db
from engine.analytics import PortfolioAnalytics


# ---------------------------------------------------------------------------
# Helper: seed portfolio_snapshots from a return series (async)
# ---------------------------------------------------------------------------

async def _seed_snapshots_from_returns(
    db_file: Path,
    returns: list[float],
    start_value: float = 100.0,
) -> list[float]:
    """Insert portfolio_snapshots rows computed from a return series.

    Computes portfolio values: v[0]=start_value, v[i]=v[i-1]*(1+returns[i-1]).
    Inserts rows with ascending timestamps so analytics ORDER BY timestamp ASC
    returns them in chronological order.

    Returns the list of values inserted.
    """
    values: list[float] = [start_value]
    for r in returns:
        values.append(values[-1] * (1.0 + r))

    now = datetime.now(timezone.utc)
    async with aiosqlite.connect(db_file) as conn:
        for i, value in enumerate(values):
            # Oldest snapshot first: offset by (len-1-i) days
            ts = (now - timedelta(days=len(values) - 1 - i)).isoformat()
            await conn.execute(
                """
                INSERT INTO portfolio_snapshots
                    (timestamp, total_value, cash, positions_json, trigger_event)
                VALUES (?, ?, ?, ?, 'test_seed')
                """,
                (ts, value, 0.0, "[]"),
            )
        await conn.commit()
    return values


# ---------------------------------------------------------------------------
# Test A: CVaR matches QuantStats reference
# ---------------------------------------------------------------------------

async def test_cvar_matches_quantstats_reference(tmp_path: Path) -> None:
    """get_portfolio_risk CVaR equals the direct qs_stats.cvar() call on same data."""
    db_file = tmp_path / "cvar.db"
    await init_db(db_file)
    returns = [-0.02, -0.01, 0.005, 0.01, -0.03, 0.02, -0.015] * 15  # 105 obs
    await _seed_snapshots_from_returns(db_file, returns, start_value=100.0)
    analytics = PortfolioAnalytics(str(db_file))
    result = await analytics.get_portfolio_risk(days=365)

    # Reference: call qs_stats.cvar directly on the same returns series
    expected_cvar_95_pct = -float(qs_stats.cvar(pd.Series(returns), confidence=0.95)) * 100
    expected_cvar_99_pct = -float(qs_stats.cvar(pd.Series(returns), confidence=0.99)) * 100

    assert result["cvar_95"] is not None, "cvar_95 should not be None for 105 obs"
    assert result["cvar_99"] is not None, "cvar_99 should not be None for 105 obs"

    assert abs(result["cvar_95"] - round(expected_cvar_95_pct, 4)) < 0.01, (
        f"cvar_95 {result['cvar_95']} != reference {expected_cvar_95_pct:.4f}"
    )
    assert abs(result["cvar_99"] - round(expected_cvar_99_pct, 4)) < 0.01, (
        f"cvar_99 {result['cvar_99']} != reference {expected_cvar_99_pct:.4f}"
    )


# ---------------------------------------------------------------------------
# Test B: Historical CVaR is materially larger than Gaussian on fat-tail series
# ---------------------------------------------------------------------------

async def test_cvar_not_gaussian_on_fat_tail(tmp_path: Path) -> None:
    """Historical-simulation CVaR exceeds equivalent Gaussian CVaR by >=1 pp on fat-tail series."""
    db_file = tmp_path / "fat.db"
    await init_db(db_file)
    # 3 huge losses + 97 small gains -- Gaussian severely underestimates CVaR
    returns = [-0.15, -0.12, -0.10] + [0.005] * 97
    await _seed_snapshots_from_returns(db_file, returns, start_value=100.0)
    analytics = PortfolioAnalytics(str(db_file))
    result = await analytics.get_portfolio_risk(days=365)

    assert result["cvar_95"] is not None, "cvar_95 should not be None"

    # Equivalent Gaussian CVaR on the same series
    mean_ret = statistics.mean(returns) * 100
    std_ret = statistics.stdev(returns) * 100
    gaussian_cvar_95_pct = -(mean_ret - std_ret * 0.10313 / 0.05)

    assert result["cvar_95"] - gaussian_cvar_95_pct > 1.0, (
        f"Historical cvar_95 {result['cvar_95']:.4f}% should exceed "
        f"Gaussian {gaussian_cvar_95_pct:.4f}% by >1 pp on fat-tail series"
    )


# ---------------------------------------------------------------------------
# Test C: CVaR 99% is >= CVaR 95% (monotonicity)
# ---------------------------------------------------------------------------

async def test_cvar_99_greater_than_cvar_95(tmp_path: Path) -> None:
    """cvar_99 >= cvar_95 (higher confidence level = larger expected loss)."""
    db_file = tmp_path / "mono.db"
    await init_db(db_file)
    returns = [-0.02, -0.01, 0.005, 0.01, -0.03, 0.02, -0.015, 0.008, -0.005, 0.012] * 12
    await _seed_snapshots_from_returns(db_file, returns, start_value=100.0)
    analytics = PortfolioAnalytics(str(db_file))
    result = await analytics.get_portfolio_risk(days=365)

    assert result["cvar_95"] is not None
    assert result["cvar_99"] is not None
    assert result["cvar_99"] >= result["cvar_95"], (
        f"cvar_99 {result['cvar_99']} should be >= cvar_95 {result['cvar_95']}"
    )


# ---------------------------------------------------------------------------
# Test D: Insufficient data (<10 snapshots) -> all risk fields None, no crash
# ---------------------------------------------------------------------------

async def test_cvar_none_when_insufficient_data(tmp_path: Path) -> None:
    """With <10 snapshots, cvar_95/cvar_99/portfolio_var are None (not crash)."""
    db_file = tmp_path / "small.db"
    await init_db(db_file)
    # Only 5 data points -> 4 returns < 10 threshold
    returns = [-0.01, 0.02, -0.005, 0.015]
    await _seed_snapshots_from_returns(db_file, returns, start_value=100.0)
    analytics = PortfolioAnalytics(str(db_file))
    result = await analytics.get_portfolio_risk(days=365)

    assert result["cvar_95"] is None, f"Expected None for cvar_95, got {result['cvar_95']}"
    assert result["cvar_99"] is None, f"Expected None for cvar_99, got {result['cvar_99']}"
    assert result["portfolio_var"] is None, (
        f"Expected None for portfolio_var, got {result['portfolio_var']}"
    )
    assert result["portfolio_var_method"] == "insufficient_data"


# ---------------------------------------------------------------------------
# Test E: matplotlib regression -- subprocess check
# ---------------------------------------------------------------------------

def test_matplotlib_not_imported_on_engine_analytics_import() -> None:
    """import engine.analytics in a fresh interpreter must not pull in matplotlib/seaborn.

    Uses a subprocess so in-process matplotlib state (from test runner or pandas_ta)
    cannot mask the leak.
    """
    code = (
        "import sys\n"
        "from engine import analytics\n"
        "banned = [m for m in sys.modules if m.startswith('matplotlib') "
        "or m.startswith('seaborn')]\n"
        "assert not banned, f'Leaked: {banned}'\n"
        "print('OK')\n"
    )
    project_root = str(Path(__file__).parent.parent)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": project_root},
    )
    assert result.returncode == 0, (
        f"matplotlib/seaborn leaked into sys.modules when importing engine.analytics:\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Test F: portfolio_var_method field is present and correct
# ---------------------------------------------------------------------------

async def test_portfolio_var_method_field_present(tmp_path: Path) -> None:
    """portfolio_var_method is 'historical_simulation' with sufficient data, 'insufficient_data' when not."""
    # Sufficient data case
    db_file_ok = tmp_path / "method_ok.db"
    await init_db(db_file_ok)
    returns = [-0.01, 0.015, -0.02, 0.005, -0.005, 0.01, -0.015, 0.008, -0.005, 0.012] * 12
    await _seed_snapshots_from_returns(db_file_ok, returns, start_value=100.0)
    analytics_ok = PortfolioAnalytics(str(db_file_ok))
    result_ok = await analytics_ok.get_portfolio_risk(days=365)
    assert result_ok.get("portfolio_var_method") == "historical_simulation", (
        f"Expected 'historical_simulation', got {result_ok.get('portfolio_var_method')!r}"
    )

    # Insufficient data case
    db_file_ins = tmp_path / "method_ins.db"
    await init_db(db_file_ins)
    returns_small = [-0.01, 0.02, -0.005]  # 3 returns < 10 threshold
    await _seed_snapshots_from_returns(db_file_ins, returns_small, start_value=100.0)
    analytics_ins = PortfolioAnalytics(str(db_file_ins))
    result_ins = await analytics_ins.get_portfolio_risk(days=365)
    assert result_ins.get("portfolio_var_method") == "insufficient_data", (
        f"Expected 'insufficient_data', got {result_ins.get('portfolio_var_method')!r}"
    )
