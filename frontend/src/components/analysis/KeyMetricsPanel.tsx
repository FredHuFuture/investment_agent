import { formatCurrency } from "../../lib/formatters";
import type { AgentSignal } from "../../api/types";

// ---------------------------------------------------------------------------
// Types & helpers
// ---------------------------------------------------------------------------
interface TickerInfoData {
  current_price?: number;
  name?: string;
  market_cap?: number;
  pe_ratio?: number;
  forward_pe?: number;
  beta?: number;
  dividend_yield?: number;
  sector?: string;
  industry?: string;
  "52w_high"?: number;
  "52w_low"?: number;
  pegRatio?: number;
  earningsGrowth?: number;
  recommendationMean?: number;
}

function formatLargeNumber(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return formatCurrency(n);
}

function fmt(v: unknown, type: "num" | "pct" | "price" | "large" | "str" = "num", decimals = 2): string | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  if (type === "str") return String(v);
  if (isNaN(n)) return null;
  switch (type) {
    case "pct":
      return `${(n * (Math.abs(n) <= 1 ? 100 : 1)).toFixed(decimals)}%`;
    case "price":
      return formatCurrency(n);
    case "large":
      return formatLargeNumber(n);
    default:
      return n.toFixed(decimals);
  }
}

function analystLabel(v: number): string {
  if (v <= 1.5) return "Strong Buy";
  if (v <= 2.5) return "Buy";
  if (v <= 3.5) return "Hold";
  if (v <= 4.5) return "Sell";
  return "Strong Sell";
}

// ---------------------------------------------------------------------------
// Stat row — key/value pair
// ---------------------------------------------------------------------------
function Stat({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="flex justify-between py-1 border-b border-gray-800/20 last:border-0">
      <span className="text-[11px] text-gray-500">{label}</span>
      <span className="text-[11px] font-mono text-gray-300">{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Card section — a titled block in the grid
// ---------------------------------------------------------------------------
function MetricSection({
  title,
  color,
  children,
}: {
  title: string;
  color: string;
  children: React.ReactNode;
}) {
  const childArray = Array.isArray(children) ? children : [children];
  const visibleCount = childArray.filter(Boolean).length;
  if (visibleCount === 0) return null;

  return (
    <div className="rounded-lg bg-gray-900/40 border border-gray-800/30 p-3">
      <div className="flex items-center gap-1.5 mb-2">
        <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
        <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
          {title}
        </span>
      </div>
      <div>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Extract agent metrics
// ---------------------------------------------------------------------------
function getAgentMetrics(agents: AgentSignal[], name: string): Record<string, unknown> {
  const agent = agents.find((a) => a.agent_name === name);
  return agent?.metrics ?? {};
}

// ---------------------------------------------------------------------------
// Main component — multi-column grid layout
// ---------------------------------------------------------------------------
interface Props {
  tickerInfo: Record<string, unknown>;
  agentSignals: AgentSignal[];
}

export default function KeyMetricsPanel({ tickerInfo, agentSignals }: Props) {
  const d = tickerInfo as TickerInfoData;
  const tech = getAgentMetrics(agentSignals, "TechnicalAgent");
  const fund = getAgentMetrics(agentSignals, "FundamentalAgent");
  const macro = getAgentMetrics(agentSignals, "MacroAgent");
  const crypto = getAgentMetrics(agentSignals, "CryptoAgent");
  const isCrypto = Object.keys(crypto).length > 0;

  const w52High = d["52w_high"];
  const w52Low = d["52w_low"];
  const price = d.current_price;

  let rangePct: number | null = null;
  if (price != null && w52High != null && w52Low != null && w52High > w52Low) {
    rangePct = ((price - w52Low) / (w52High - w52Low)) * 100;
  }

  return (
    <div className="space-y-4">
      {/* Ticker header bar */}
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        {d.name && <span className="text-sm text-gray-300">{d.name}</span>}
        {price != null && (
          <span className="text-lg font-semibold font-mono text-white">
            {formatCurrency(price)}
          </span>
        )}
        {(d.sector || d.industry) && (
          <span className="text-[11px] text-gray-500">
            {[d.sector, d.industry].filter(Boolean).join(" / ")}
          </span>
        )}
        {/* 52-week range inline */}
        {rangePct != null && w52Low != null && w52High != null && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-[10px] text-gray-600">52W</span>
            <span className="text-[10px] font-mono text-gray-500">{formatCurrency(w52Low)}</span>
            <div className="w-24 h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500"
                style={{ width: `${Math.min(100, Math.max(0, rangePct))}%` }}
              />
            </div>
            <span className="text-[10px] font-mono text-gray-500">{formatCurrency(w52High)}</span>
          </div>
        )}
      </div>

      {/* Multi-column metrics grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {/* ── Valuation ── */}
        <MetricSection title="Valuation" color="bg-accent-light">
          <Stat label="P/E (TTM)" value={fmt(d.pe_ratio ?? fund.pe_trailing)} />
          <Stat label="Forward P/E" value={fmt(d.forward_pe ?? fund.pe_forward)} />
          <Stat label="PEG Ratio" value={fmt(d.pegRatio ?? fund.peg_ratio)} />
          <Stat label="P/B Ratio" value={fmt(fund.pb_ratio)} />
          <Stat label="EV/EBITDA" value={fmt(fund.ev_ebitda)} />
          <Stat label="FCF Yield" value={fund.fcf_yield != null ? fmt(fund.fcf_yield, "pct", 1) : null} />
          <Stat label="Market Cap" value={fmt(d.market_cap ?? fund.market_cap, "large")} />
          <Stat label="% from 52W High" value={fund.pct_from_52w_high != null ? `${Number(fund.pct_from_52w_high).toFixed(1)}%` : null} />
        </MetricSection>

        {/* ── Quality ── */}
        <MetricSection title="Quality" color="bg-emerald-400">
          <Stat label="ROE" value={fund.roe != null ? fmt(fund.roe, "pct", 1) : null} />
          <Stat label="Profit Margin" value={fund.profit_margin != null ? fmt(fund.profit_margin, "pct", 1) : null} />
          <Stat label="Debt / Equity" value={fmt(fund.debt_equity)} />
          <Stat label="Current Ratio" value={fmt(fund.current_ratio)} />
          <Stat label="Beta" value={fmt(d.beta)} />
          <Stat
            label="Analyst Rating"
            value={
              (d.recommendationMean ?? fund.analyst_rating) != null
                ? `${Number(d.recommendationMean ?? fund.analyst_rating).toFixed(1)} (${analystLabel(Number(d.recommendationMean ?? fund.analyst_rating))})`
                : null
            }
          />
        </MetricSection>

        {/* ── Growth ── */}
        <MetricSection title="Growth" color="bg-violet-400">
          <Stat label="Revenue Growth" value={fund.revenue_growth != null ? fmt(fund.revenue_growth, "pct", 1) : null} />
          <Stat label="Earnings Growth" value={(d.earningsGrowth ?? fund.earnings_growth) != null ? fmt(d.earningsGrowth ?? fund.earnings_growth, "pct", 1) : null} />
          <Stat label="Dividend Yield" value={(d.dividend_yield ?? fund.dividend_yield) != null ? `${(Number(d.dividend_yield ?? fund.dividend_yield) * 100).toFixed(2)}%` : null} />
        </MetricSection>

        {/* ── Technical ── */}
        <MetricSection title="Technical" color="bg-amber-400">
          <Stat label="RSI (14)" value={fmt(tech.rsi_14)} />
          <Stat label="SMA 20" value={fmt(tech.sma_20, "price")} />
          <Stat label="SMA 50" value={fmt(tech.sma_50, "price")} />
          <Stat label="SMA 200" value={fmt(tech.sma_200, "price")} />
          <Stat label="MACD" value={fmt(tech.macd_line, "num", 3)} />
          <Stat label="MACD Signal" value={fmt(tech.macd_signal, "num", 3)} />
          <Stat label="MACD Hist" value={fmt(tech.macd_histogram, "num", 3)} />
          <Stat label="BB Upper" value={fmt(tech.bb_upper, "price")} />
          <Stat label="BB Lower" value={fmt(tech.bb_lower, "price")} />
          <Stat label="ATR (14)" value={fmt(tech.atr_14)} />
          <Stat label="Vol Ratio" value={fmt(tech.volume_ratio, "num", 2)} />
          <Stat label="Weekly Confirms" value={tech.weekly_trend_confirms != null ? (tech.weekly_trend_confirms ? "Yes" : "No") : null} />
        </MetricSection>

        {/* ── Macro ── */}
        <MetricSection title="Macro" color="bg-rose-400">
          <Stat label="Regime" value={fmt(macro.regime, "str")} />
          <Stat label="VIX" value={fmt(macro.vix_current)} />
          <Stat label="VIX SMA(20)" value={fmt(macro.vix_sma_20)} />
          <Stat label="Fed Funds" value={macro.fed_funds_rate != null ? `${Number(macro.fed_funds_rate).toFixed(2)}%` : null} />
          <Stat label="Fed Trend" value={fmt(macro.fed_funds_trend, "str")} />
          <Stat label="10Y Treasury" value={macro.treasury_10y != null ? `${Number(macro.treasury_10y).toFixed(2)}%` : null} />
          <Stat label="2Y Treasury" value={macro.treasury_2y != null ? `${Number(macro.treasury_2y).toFixed(2)}%` : null} />
          <Stat label="Yield Curve" value={macro.yield_curve_spread != null ? `${Number(macro.yield_curve_spread).toFixed(2)}%` : null} />
          <Stat label="M2 YoY" value={macro.m2_yoy_growth != null ? `${Number(macro.m2_yoy_growth).toFixed(1)}%` : null} />
        </MetricSection>

        {/* ── Agent Scores ── */}
        <MetricSection title="Agent Scores" color="bg-gray-400">
          {agentSignals.map((a) => {
            const m = a.metrics as Record<string, unknown>;
            return (
              <div key={a.agent_name} className="mb-1">
                <div className="text-[10px] text-gray-500 font-medium mt-1">{a.agent_name.replace("Agent", "")}</div>
                <Stat label="Composite" value={fmt(m.composite_score)} />
                {m.trend_score != null && <Stat label="Trend" value={fmt(m.trend_score)} />}
                {m.momentum_score != null && <Stat label="Momentum" value={fmt(m.momentum_score)} />}
                {m.volatility_score != null && <Stat label="Volatility" value={fmt(m.volatility_score)} />}
                {m.value_score != null && <Stat label="Value" value={fmt(m.value_score)} />}
                {m.quality_score != null && <Stat label="Quality" value={fmt(m.quality_score)} />}
                {m.growth_score != null && <Stat label="Growth" value={fmt(m.growth_score)} />}
                {m.net_score != null && <Stat label="Net Score" value={fmt(m.net_score)} />}
                {m.risk_on_points != null && <Stat label="Risk-On" value={fmt(m.risk_on_points)} />}
                {m.risk_off_points != null && <Stat label="Risk-Off" value={fmt(m.risk_off_points)} />}
              </div>
            );
          })}
        </MetricSection>

        {/* ── Crypto (only for BTC/ETH) ── */}
        {isCrypto && (
          <MetricSection title="Crypto Factors" color="bg-cyan-400">
            <Stat label="Market Cap" value={fmt(crypto.market_cap, "large")} />
            <Stat label="Dominance" value={fmt(crypto.dominance_signal, "str")} />
            <Stat label="Supply Ratio" value={crypto.supply_ratio != null ? `${(Number(crypto.supply_ratio) * 100).toFixed(1)}%` : null} />
            <Stat label="Return 3M" value={crypto.return_3m_pct != null ? `${Number(crypto.return_3m_pct).toFixed(1)}%` : null} />
            <Stat label="Return 6M" value={crypto.return_6m_pct != null ? `${Number(crypto.return_6m_pct).toFixed(1)}%` : null} />
            <Stat label="Return 12M" value={crypto.return_12m_pct != null ? `${Number(crypto.return_12m_pct).toFixed(1)}%` : null} />
            <Stat label="ATH Distance" value={crypto.ath_distance_pct != null ? `${Number(crypto.ath_distance_pct).toFixed(1)}%` : null} />
            <Stat label="Vol 30d" value={crypto.volatility_30d_pct != null ? `${Number(crypto.volatility_30d_pct).toFixed(1)}%` : null} />
            <Stat label="Max DD 90d" value={crypto.max_drawdown_90d_pct != null ? `${Number(crypto.max_drawdown_90d_pct).toFixed(1)}%` : null} />
            <Stat label="Sharpe 90d" value={fmt(crypto.sharpe_90d)} />
            <Stat label="S&P Corr" value={fmt(crypto.sp500_correlation_90d)} />
            <Stat label="VIX" value={fmt(crypto.vix_level)} />
            <Stat label="Cycle Phase" value={fmt(crypto.cycle_phase, "str")} />
            <Stat label="Fear/Greed" value={fmt(crypto.fear_greed_proxy)} />
            <Stat label="ETF Access" value={crypto.etf_access != null ? (crypto.etf_access ? "Yes" : "No") : null} />
            <Stat label="Bear Survivals" value={crypto.bear_survivals != null ? String(crypto.bear_survivals) : null} />
          </MetricSection>
        )}
      </div>
    </div>
  );
}
