"""CLI for generating interactive HTML charts from analysis and portfolio data."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import webbrowser
from datetime import datetime, timezone

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pandas as pd
import pandas_ta as ta

from charts.analysis_charts import (
    create_agent_breakdown_chart,
    create_crypto_factor_chart,
    create_price_chart,
)
from charts.portfolio_charts import create_allocation_chart, create_sector_chart
from charts.tracking_charts import create_calibration_chart, create_drift_scatter
from data_providers.factory import get_provider
from db.database import DEFAULT_DB_PATH
from engine.drift_analyzer import DriftAnalyzer
from engine.pipeline import AnalysisPipeline
from portfolio.manager import PortfolioManager
from tracking.store import SignalStore
from tracking.tracker import SignalTracker

# Auto-detect crypto tickers (case-insensitive)
_CRYPTO_TICKERS = {"BTC", "ETH", "BTC-USD", "ETH-USD"}
_CRYPTO_YF_MAP = {"BTC": "BTC-USD", "ETH": "ETH-USD"}

DEFAULT_OUTPUT_DIR = "data/charts"

_FREQ_MAP = {"daily": "B", "weekly": "W-MON", "monthly": "BMS"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="charts",
        description="Generate interactive HTML charts.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Save chart HTML without opening browser.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for HTML files (default: {DEFAULT_OUTPUT_DIR}).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    analysis_parser = subparsers.add_parser(
        "analysis", help="Run fresh analysis and show price + agent charts."
    )
    analysis_parser.add_argument("ticker", help="Ticker symbol (e.g. AAPL, BTC-USD).")
    analysis_parser.add_argument(
        "--asset-type", default="stock", choices=["stock", "btc", "eth"],
        help="Asset type (default: stock).",
    )
    analysis_parser.add_argument(
        "--min-confidence", type=float, default=70.0,
        help="Minimum confidence %% to show signal markers (default: 70).",
    )
    analysis_parser.add_argument(
        "--signal-freq", default="weekly",
        choices=["daily", "weekly", "monthly"],
        help="Frequency for historical signal scan (default: weekly).",
    )
    analysis_parser.add_argument(
        "--no-signals", action="store_true",
        help="Skip historical signal overlay on price chart.",
    )

    subparsers.add_parser("portfolio", help="Portfolio allocation and sector charts.")

    calibration_parser = subparsers.add_parser(
        "calibration", help="Signal confidence calibration chart."
    )
    calibration_parser.add_argument(
        "--lookback", type=int, default=100,
        help="Number of signals to look back (default: 100).",
    )

    subparsers.add_parser("drift", help="Expected vs actual return scatter.")

    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_and_open(fig, name: str, output_dir: str, no_open: bool) -> str:
    """Write figure to HTML file and optionally open in browser. Returns file path."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{ts}.html"
    filepath = os.path.join(output_dir, filename)
    fig.write_html(filepath, include_plotlyjs=True)
    print(f"  Saved: {filepath}")
    if not no_open:
        webbrowser.open(f"file://{os.path.abspath(filepath)}")
    return filepath


async def _generate_historical_signals(
    ohlcv: pd.DataFrame,
    ticker: str,
    asset_type: str,
    frequency: str = "weekly",
) -> list[dict]:
    """Walk-forward TechnicalAgent signals (PIT-safe, no API calls).

    Uses TechnicalAgent for all asset types because:
    - It is fully PIT-safe (no lookahead bias).
    - It requires only OHLCV data (fast, no network calls).
    - RSI / MACD / SMA / Bollinger apply to any price series.
    """
    from agents.models import AgentInput
    from agents.technical import TechnicalAgent
    from backtesting.data_slicer import HistoricalDataProvider

    freq = _FREQ_MAP.get(frequency, "W-MON")

    # Skip first 200 rows for SMA200 warmup
    warmup = min(200, len(ohlcv) - 1)
    start = ohlcv.index[warmup]
    end = ohlcv.index[-1]

    dates = pd.bdate_range(start=start, end=end, freq=freq)
    available = set(ohlcv.index.normalize())
    dates = [d for d in dates if d.normalize() in available]

    if not dates:
        return []

    agent_input = AgentInput(ticker=ticker, asset_type=asset_type)
    results: list[dict] = []

    for date in dates:
        provider = HistoricalDataProvider(ohlcv, str(date.date()))
        agent = TechnicalAgent(provider)
        try:
            out = await agent.analyze(agent_input)
            results.append({
                "date": date,
                "signal": out.signal,
                "confidence": out.confidence,
                "reasoning": out.reasoning,
                "metrics": out.metrics,
            })
        except Exception:
            pass  # skip dates where analysis fails

    return results


def _prepare_signal_data(
    signals: list[dict], ohlcv: pd.DataFrame,
) -> list[dict]:
    """Convert walk-forward signals to JSON-serializable dicts."""
    result: list[dict] = []
    for s in signals:
        date = s["date"]
        mask = ohlcv.index.normalize() == date.normalize()
        if not mask.any():
            continue

        low = float(ohlcv.loc[mask, "Low"].iloc[0])
        high = float(ohlcv.loc[mask, "High"].iloc[0])

        m = s.get("metrics") or {}
        result.append({
            "date": date.strftime("%Y-%m-%d"),
            "signal": s["signal"].value,
            "confidence": round(s["confidence"], 1),
            "low": round(low, 4),
            "high": round(high, 4),
            "reasoning": s.get("reasoning", ""),
            "metrics": {
                k: round(v, 4) if isinstance(v, float) else v
                for k, v in m.items() if v is not None
            },
        })
    return result


# ---------------------------------------------------------------------------
# Interactive HTML builder
# ---------------------------------------------------------------------------

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#111;color:#eee;font-family:-apple-system,BlinkMacSystemFont,sans-serif}
.container{display:flex;height:100vh}
.chart-area{flex:1;overflow-y:auto;padding:15px}
.detail-panel{width:340px;border-left:1px solid #333;overflow-y:auto;padding:16px;
  display:flex;flex-direction:column;background:#151515}
.controls{display:flex;align-items:center;gap:12px;margin-bottom:10px;
  padding:8px 14px;background:rgba(40,40,40,0.9);border-radius:6px}
.controls label{font-size:13px;color:#aaa;white-space:nowrap}
.controls input[type=range]{flex:1;accent-color:#00CC66}
.controls .val{font-size:14px;font-weight:bold;min-width:38px;text-align:center}
.controls .cnt{font-size:12px;color:#666;white-space:nowrap}
.panel-header{font-size:15px;font-weight:bold;border-bottom:1px solid #333;
  padding-bottom:8px;margin-bottom:12px;color:#aaa}
.panel-placeholder{color:#555;font-size:13px;margin-top:30px;text-align:center;line-height:1.5}
.signal-badge{display:inline-block;padding:2px 10px;border-radius:4px;
  font-weight:bold;font-size:18px}
.signal-buy{background:rgba(0,204,102,0.15);color:#00CC66}
.signal-sell{background:rgba(204,51,51,0.15);color:#CC3333}
.detail-section{margin-bottom:16px}
.detail-section-title{font-size:10px;text-transform:uppercase;letter-spacing:1.2px;
  color:#555;margin-bottom:6px;font-weight:600}
.score-row{display:flex;align-items:center;margin:4px 0;font-size:12px}
.score-label{width:88px;color:#888;flex-shrink:0}
.score-bar-bg{flex:1;height:14px;background:#1a1a1a;border-radius:3px;
  position:relative;overflow:hidden}
.score-bar-center{position:absolute;left:50%;top:0;bottom:0;width:1px;background:#333}
.score-bar-fill{position:absolute;top:1px;bottom:1px;border-radius:2px;transition:width .2s}
.score-val{width:42px;text-align:right;font-size:12px;font-weight:bold;flex-shrink:0}
.ind-table{width:100%;font-size:12px;border-collapse:collapse}
.ind-table td{padding:4px 0;border-bottom:1px solid #1a1a1a}
.ind-table td:first-child{color:#666}
.ind-table td:last-child{text-align:right;color:#ccc}
.reasoning-text{font-size:12px;color:#aaa;line-height:1.55}
"""

_JS_APP = r"""
(function(){
'use strict';
var G='#00CC66',R='#CC3333',H='#888888';
var priceSpec=JSON.parse(document.getElementById('d-price').textContent);
var agentSpec=JSON.parse(document.getElementById('d-agent').textContent);
var allSignals=JSON.parse(document.getElementById('d-signals').textContent);
var threshold=parseInt(document.getElementById('d-threshold').textContent);
var priceDiv=document.getElementById('price-chart');
var agentDiv=document.getElementById('agent-chart');
var cfg={responsive:true,displayModeBar:true,
  modeBarButtonsToRemove:['lasso2d','select2d']};
Plotly.newPlot(priceDiv,priceSpec.data,priceSpec.layout,cfg).then(function(){
  if(allSignals.length){addTraces();attachClick();}
});
Plotly.newPlot(agentDiv,agentSpec.data,agentSpec.layout,cfg);

/* Normalize date to YYYY-MM-DD (Plotly may return "2024-01-15 00:00" etc.) */
function normDate(d){return String(d).slice(0,10);}

function filt(){
  return{
    buys:allSignals.filter(function(s){return s.signal==='BUY'&&s.confidence>=threshold}),
    sells:allSignals.filter(function(s){return s.signal==='SELL'&&s.confidence>=threshold})
  };
}
function addTraces(){
  var f=filt();
  Plotly.addTraces(priceDiv,[
    {x:f.buys.map(function(s){return s.date}),
     y:f.buys.map(function(s){return s.low*0.97}),
     mode:'markers',type:'scatter',
     marker:{symbol:'triangle-up',size:13,color:G,line:{width:1,color:'white'}},
     name:'BUY (>='+threshold+'%)',hoverinfo:'none'},
    {x:f.sells.map(function(s){return s.date}),
     y:f.sells.map(function(s){return s.high*1.03}),
     mode:'markers',type:'scatter',
     marker:{symbol:'triangle-down',size:13,color:R,line:{width:1,color:'white'}},
     name:'SELL (>='+threshold+'%)',hoverinfo:'none'}
  ]);
  updCount(f);
}
function findIdx(prefix){
  for(var i=0;i<priceDiv.data.length;i++){
    if((priceDiv.data[i].name||'').indexOf(prefix)===0) return i;
  }return -1;
}
function updTraces(){
  var f=filt();var bi=findIdx('BUY'),si=findIdx('SELL');
  if(bi>=0) Plotly.restyle(priceDiv,{
    x:[f.buys.map(function(s){return s.date})],
    y:[f.buys.map(function(s){return s.low*0.97})],
    name:'BUY (>='+threshold+'%)'
  },[bi]);
  if(si>=0) Plotly.restyle(priceDiv,{
    x:[f.sells.map(function(s){return s.date})],
    y:[f.sells.map(function(s){return s.high*1.03})],
    name:'SELL (>='+threshold+'%)'
  },[si]);
  updCount(f);
}
function updCount(f){
  var el=document.getElementById('signal-count');
  if(el) el.textContent=f.buys.length+' BUY + '+f.sells.length+' SELL';
}
function attachClick(){
  priceDiv.on('plotly_click',function(data){
    var pt=data.points[0];var tn=pt.data.name||'';
    if(tn.indexOf('BUY')!==0&&tn.indexOf('SELL')!==0) return;
    var sig=tn.indexOf('BUY')===0?'BUY':'SELL';
    var dt=normDate(pt.x);
    var match=allSignals.find(function(s){return s.signal===sig&&normDate(s.date)===dt});
    if(match) showDetail(match);
  });
}
function showDetail(s){
  var p=document.getElementById('detail-content');
  var m=s.metrics||{};var c=s.signal==='BUY'?G:R;
  var bc=s.signal==='BUY'?'signal-buy':'signal-sell';
  var h='<div style="margin-bottom:14px">';
  h+='<div style="color:#666;font-size:13px;margin-bottom:4px">'+s.date+'</div>';
  h+='<span class="signal-badge '+bc+'">'+s.signal+'</span>';
  h+=' <span style="font-size:20px;font-weight:bold">'+s.confidence.toFixed(0)+'%</span></div>';
  var scores=[['Trend',m.trend_score],['Momentum',m.momentum_score],
    ['Volatility',m.volatility_score]];
  scores=scores.filter(function(x){return x[1]!=null});
  if(scores.length){
    h+='<div class="detail-section"><div class="detail-section-title">Sub-Scores</div>';
    scores.forEach(function(x){
      var nm=x[0],v=x[1],cl=v>=0?G:R;
      var pct=Math.min(Math.abs(v),50)*2;
      var side=v>=0?'left:50%':'right:50%';
      h+='<div class="score-row"><span class="score-label">'+nm+'</span>';
      h+='<div class="score-bar-bg"><div class="score-bar-center"></div>';
      h+='<div class="score-bar-fill" style="'+side+';width:'+pct+'%;background:'+cl+'"></div></div>';
      h+='<span class="score-val" style="color:'+cl+'">'+(v>=0?'+':'')+v.toFixed(0)+'</span></div>';
    });
    h+='</div>';
  }
  var comp=m.composite_score;
  if(comp!=null){
    h+='<div class="detail-section"><div class="detail-section-title">Composite</div>';
    h+='<div style="font-size:22px;font-weight:bold;color:'+(comp>=0?G:R)+'">';
    h+=(comp>=0?'+':'')+comp.toFixed(0)+'</div></div>';
  }
  var inds=[['RSI (14)',m.rsi_14,function(v){return v.toFixed(1)}],
    ['MACD Hist',m.macd_histogram,function(v){return(v>=0?'+':'')+v.toFixed(3)}],
    ['Vol Ratio',m.volume_ratio,function(v){return v.toFixed(2)+'x'}],
    ['Price',m.current_price,function(v){return '$'+v.toFixed(2)}],
    ['SMA 20',m.sma_20,function(v){return '$'+v.toFixed(2)}],
    ['SMA 50',m.sma_50,function(v){return '$'+v.toFixed(2)}],
    ['SMA 200',m.sma_200,function(v){return '$'+v.toFixed(2)}]
  ].filter(function(x){return x[1]!=null});
  if(inds.length){
    h+='<div class="detail-section"><div class="detail-section-title">Indicators</div>';
    h+='<table class="ind-table">';
    inds.forEach(function(x){
      h+='<tr><td>'+x[0]+'</td><td>'+x[2](x[1])+'</td></tr>';
    });
    h+='</table></div>';
  }
  if(s.reasoning){
    h+='<div class="detail-section"><div class="detail-section-title">Analysis</div>';
    h+='<div class="reasoning-text">'+s.reasoning+'</div></div>';
  }
  p.innerHTML=h;
}
var slider=document.getElementById('threshold-slider');
if(slider){
  slider.addEventListener('input',function(){
    threshold=parseInt(this.value);
    document.getElementById('threshold-val').textContent=threshold;
    updTraces();
  });
}
})();
"""


def _save_interactive_html(
    price_fig,
    agent_fig,
    signal_data: list[dict],
    min_confidence: float,
    name: str,
    output_dir: str,
    no_open: bool,
) -> str:
    """Generate interactive HTML with click-to-detail panel + threshold slider."""
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"{name}_{ts}.html")

    price_json = price_fig.to_json()
    agent_json = agent_fig.to_json()
    signals_json = json.dumps(signal_data)

    # Get bundled plotly.js for offline support
    from plotly.offline import get_plotlyjs
    plotly_js = get_plotlyjs()

    has_signals = len(signal_data) > 0

    # Controls bar (only when signals present)
    controls = ""
    if has_signals:
        controls = (
            '<div class="controls">'
            '<label>Confidence Threshold:</label>'
            f'<input type="range" id="threshold-slider" min="0" max="100"'
            f' value="{int(min_confidence)}" step="5">'
            f'<span class="val" id="threshold-val">{int(min_confidence)}</span>'
            '<span class="val">%</span>'
            '<span class="cnt" id="signal-count"></span>'
            '</div>'
        )

    # Right panel (only when signals present)
    panel = ""
    if has_signals:
        panel = (
            '<div class="detail-panel">'
            '<div class="panel-header">Signal Analysis</div>'
            '<div id="detail-content">'
            '<div class="panel-placeholder">'
            'Click a <span style="color:#00CC66">&#9650;</span> or '
            '<span style="color:#CC3333">&#9660;</span> marker<br>'
            'on the price chart to see<br>the full analysis breakdown.'
            '</div></div></div>'
        )

    body = (
        '<div class="container">'
        '<div class="chart-area">'
        f'{controls}'
        '<div id="price-chart"></div>'
        '<div id="agent-chart" style="margin-top:10px"></div>'
        '</div>'
        f'{panel}'
        '</div>'
    )

    html = (
        '<!DOCTYPE html>\n<html>\n<head>\n'
        f'<title>{name}</title>\n'
        f'<style>{_CSS}</style>\n'
        '</head>\n<body>\n'
        f'{body}\n'
        f'<script type="application/json" id="d-price">{price_json}</script>\n'
        f'<script type="application/json" id="d-agent">{agent_json}</script>\n'
        f'<script type="application/json" id="d-signals">{signals_json}</script>\n'
        f'<script type="application/json" id="d-threshold">{int(min_confidence)}</script>\n'
        f'<script>{plotly_js}</script>\n'
        f'<script>{_JS_APP}</script>\n'
        '</body>\n</html>'
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved: {filepath}")
    if not no_open:
        webbrowser.open(f"file://{os.path.abspath(filepath)}")
    return filepath


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def _cmd_analysis(
    ticker: str,
    asset_type: str,
    output_dir: str,
    no_open: bool,
    min_confidence: float = 70.0,
    signal_freq: str = "weekly",
    no_signals: bool = False,
) -> None:
    async def _run() -> None:
        # Map bare crypto tickers to yfinance symbols
        yf_ticker = (
            _CRYPTO_YF_MAP.get(ticker, ticker)
            if asset_type in ("btc", "eth")
            else ticker
        )
        print(f"Running analysis for {yf_ticker} ({asset_type})...")

        # 1. Run current analysis via full pipeline
        pipeline = AnalysisPipeline()
        signal = await pipeline.analyze_ticker(yf_ticker, asset_type)

        # 2. Fetch 2 years of OHLCV (enough for SMA200 warmup + signal history)
        provider = get_provider(asset_type)
        ohlcv = await provider.get_price_history(yf_ticker, period="2y")

        # 3. Compute technical indicators for chart overlay
        close = ohlcv["Close"]

        sma_20 = ta.sma(close, length=20)
        sma_50 = ta.sma(close, length=50)
        sma_200 = ta.sma(close, length=200)
        rsi_14 = ta.rsi(close, length=14)
        bbands = ta.bbands(close, length=20, std=2.0)

        bb_upper = None
        bb_lower = None
        if bbands is not None and not bbands.empty:
            upper_cols = [c for c in bbands.columns if "BBU" in c]
            lower_cols = [c for c in bbands.columns if "BBL" in c]
            if upper_cols:
                bb_upper = bbands[upper_cols[0]]
            if lower_cols:
                bb_lower = bbands[lower_cols[0]]

        indicators = {
            "sma_20": sma_20,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "rsi_14": rsi_14,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
        }

        # 4. Build price chart (without signal markers -- JS handles them)
        price_fig = create_price_chart(ohlcv, yf_ticker, indicators)

        # 5. Generate historical signals
        signal_data: list[dict] = []
        if not no_signals:
            print(f"  Generating historical signals ({signal_freq})...")
            hist_signals = await _generate_historical_signals(
                ohlcv, yf_ticker, asset_type, signal_freq,
            )
            if hist_signals:
                signal_data = _prepare_signal_data(hist_signals, ohlcv)
                from agents.models import Signal as Sig
                n_buy = sum(
                    1 for s in hist_signals
                    if s["signal"] == Sig.BUY and s["confidence"] >= min_confidence
                )
                n_sell = sum(
                    1 for s in hist_signals
                    if s["signal"] == Sig.SELL and s["confidence"] >= min_confidence
                )
                print(
                    f"  Found {n_buy} BUY + {n_sell} SELL signals"
                    f" (>={min_confidence:.0f}% confidence)"
                )
            else:
                print("  No historical signals generated.")

        # 6. Build agent breakdown chart
        if asset_type in ("btc", "eth") and signal.agent_signals:
            agent_fig = create_crypto_factor_chart(signal.agent_signals[0])
        else:
            agent_fig = create_agent_breakdown_chart(signal.agent_signals)

        # 7. Write interactive HTML
        _save_interactive_html(
            price_fig,
            agent_fig,
            signal_data,
            min_confidence,
            f"analysis_{yf_ticker}",
            output_dir,
            no_open,
        )

        print(
            f"\nSignal: {signal.final_signal.value}"
            f"  Confidence: {signal.final_confidence:.0f}%"
        )
        if signal.warnings:
            for w in signal.warnings:
                print(f"  Warning: {w}")

    asyncio.run(_run())


def _cmd_portfolio(output_dir: str, no_open: bool) -> None:
    async def _run() -> None:
        db_path = str(DEFAULT_DB_PATH)
        manager = PortfolioManager(db_path)
        portfolio = await manager.load_portfolio()

        alloc_fig = create_allocation_chart(portfolio)
        _save_and_open(alloc_fig, "portfolio_allocation", output_dir, no_open)

        sector_fig = create_sector_chart(portfolio)
        _save_and_open(sector_fig, "portfolio_sectors", output_dir, no_open)

    asyncio.run(_run())


def _cmd_calibration(lookback: int, output_dir: str, no_open: bool) -> None:
    async def _run() -> None:
        db_path = str(DEFAULT_DB_PATH)
        store = SignalStore(db_path)
        tracker = SignalTracker(store)
        data = await tracker.compute_calibration_data(lookback=lookback)
        fig = create_calibration_chart(data)
        _save_and_open(fig, "calibration", output_dir, no_open)

    asyncio.run(_run())


def _cmd_drift(output_dir: str, no_open: bool) -> None:
    async def _run() -> None:
        db_path = str(DEFAULT_DB_PATH)
        analyzer = DriftAnalyzer(db_path)

        # Collect drift summaries for all theses
        import aiosqlite
        drift_data: list[dict] = []
        try:
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                rows = await (
                    await conn.execute(
                        """
                        SELECT pt.id, pt.ticker, pt.expected_return_pct,
                               sh.outcome, sh.outcome_return_pct
                        FROM positions_thesis pt
                        LEFT JOIN signal_history sh ON sh.thesis_id = pt.id
                        WHERE sh.outcome IN ('WIN', 'LOSS')
                        """
                    )
                ).fetchall()
                for row in rows:
                    drift_data.append({
                        "ticker": row["ticker"],
                        "expected_return_pct": row["expected_return_pct"],
                        "actual_return_pct": row["outcome_return_pct"],
                        "outcome": row["outcome"],
                    })
        except Exception as exc:
            print(f"  Warning: could not load drift data: {exc}")

        fig = create_drift_scatter(drift_data)
        _save_and_open(fig, "drift_scatter", output_dir, no_open)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "analysis":
        ticker_upper = args.ticker.upper()
        asset_type = args.asset_type
        if asset_type == "stock" and ticker_upper in _CRYPTO_TICKERS:
            asset_type = "btc" if ticker_upper in ("BTC", "BTC-USD") else "eth"
        _cmd_analysis(
            ticker_upper,
            asset_type,
            args.output_dir,
            args.no_open,
            args.min_confidence,
            args.signal_freq,
            args.no_signals,
        )
    elif args.command == "portfolio":
        _cmd_portfolio(args.output_dir, args.no_open)
    elif args.command == "calibration":
        _cmd_calibration(args.lookback, args.output_dir, args.no_open)
    elif args.command == "drift":
        _cmd_drift(args.output_dir, args.no_open)


if __name__ == "__main__":
    main()
