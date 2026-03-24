import { useApi } from "../hooks/useApi";
import { getWeights } from "../api/endpoints";
import type { WeightsData } from "../api/types";
import { Card, CardBody } from "../components/ui/Card";
import { SkeletonCard } from "../components/ui/Skeleton";
import ErrorAlert from "../components/shared/ErrorAlert";
import { usePageTitle } from "../hooks/usePageTitle";

// ---------------------------------------------------------------------------
// Color palettes
// ---------------------------------------------------------------------------
const STOCK_PALETTE: Record<string, string> = {
  FundamentalAgent: "#10B981",
  TechnicalAgent: "#32af78",
  MacroAgent: "#F59E0B",
};

const FACTOR_PALETTE: Record<string, string> = {
  momentum_trend: "#8B5CF6",
  market_structure: "#6366F1",
  volatility_risk: "#EC4899",
  macro_correlation: "#14B8A6",
  cycle_timing: "#F97316",
  liquidity_volume: "#06B6D4",
  network_adoption: "#A855F7",
};

// ---------------------------------------------------------------------------
// SVG Donut Ring
// ---------------------------------------------------------------------------
interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

function DonutChart({
  segments,
  size = 180,
  stroke = 22,
}: {
  segments: DonutSegment[];
  size?: number;
  stroke?: number;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  let accumulated = 0;
  const arcs = segments.map((seg) => {
    const dashLength = (seg.value / 100) * circumference;
    const dashOffset = -(accumulated / 100) * circumference;
    accumulated += seg.value;
    return { ...seg, dashLength, dashOffset };
  });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Background ring */}
      <circle
        cx={center}
        cy={center}
        r={radius}
        fill="none"
        stroke="rgba(55,65,81,0.3)"
        strokeWidth={stroke}
      />
      {/* Segments */}
      {arcs.map((arc) => (
        <circle
          key={arc.label}
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={arc.color}
          strokeWidth={stroke}
          strokeDasharray={`${arc.dashLength} ${circumference - arc.dashLength}`}
          strokeDashoffset={arc.dashOffset}
          strokeLinecap="butt"
          transform={`rotate(-90 ${center} ${center})`}
          className="transition-all duration-500"
        />
      ))}
      {/* Center label */}
      <text
        x={center}
        y={center - 6}
        textAnchor="middle"
        className="fill-gray-500 text-[10px]"
      >
        TOTAL
      </text>
      <text
        x={center}
        y={center + 12}
        textAnchor="middle"
        className="fill-white text-lg font-bold"
      >
        100%
      </text>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Weight legend row
// ---------------------------------------------------------------------------
function WeightRow({
  color,
  label,
  pct,
  description,
}: {
  color: string;
  label: string;
  pct: number;
  description?: string;
}) {
  return (
    <div className="flex items-center gap-3 py-2 border-b border-gray-800/30 last:border-0">
      <span
        className="w-2.5 h-2.5 rounded-full shrink-0"
        style={{ backgroundColor: color }}
      />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-gray-200">{label}</div>
        {description && (
          <div className="text-[11px] text-gray-600 truncate">{description}</div>
        )}
      </div>
      <span className="text-sm font-mono font-medium text-gray-400 tabular-nums shrink-0">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatFactorName(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function agentShortName(name: string): string {
  return name.replace("Agent", "");
}

const FACTOR_DESCRIPTIONS: Record<string, string> = {
  momentum_trend: "3/6/12-month returns, ATH distance, SMA200",
  market_structure: "BTC dominance, supply scarcity ratio",
  volatility_risk: "30d vol, 90d drawdown, Sharpe ratio",
  macro_correlation: "S&P 500 correlation, VIX sensitivity",
  cycle_timing: "Halving cycle position, fear/greed proxy",
  liquidity_volume: "Daily USD volume, volume trend, turnover",
  network_adoption: "Age, ETF access, regulatory status",
};

const AGENT_DESCRIPTIONS: Record<string, string> = {
  FundamentalAgent: "PEG, earnings growth, analyst rating, dividends",
  TechnicalAgent: "RSI, MACD, Bollinger Bands, SMA crossovers",
  MacroAgent: "Fed funds rate, yield curve, VIX, unemployment",
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function WeightsPage() {
  usePageTitle("Weights");
  const { data, loading, error, refetch } = useApi<WeightsData>(() => getWeights());

  if (loading)
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Model Weights</h1>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SkeletonCard className="h-[280px]" />
          <SkeletonCard className="h-[280px]" />
        </div>
      </div>
    );

  if (error) return <ErrorAlert message={error} onRetry={refetch} />;
  if (!data) return null;

  const stockWeights = data.weights["stock"];
  const cryptoFactors = data.crypto_factor_weights;

  const stockSegments: DonutSegment[] = stockWeights
    ? Object.entries(stockWeights)
        .sort(([, a], [, b]) => b - a)
        .map(([agent, w]) => ({
          label: agent,
          value: w * 100,
          color: STOCK_PALETTE[agent] ?? "#6B7280",
        }))
    : [];

  const cryptoSegments: DonutSegment[] = cryptoFactors
    ? Object.entries(cryptoFactors)
        .sort(([, a], [, b]) => b - a)
        .map(([factor, w]) => ({
          label: factor,
          value: w * 100,
          color: FACTOR_PALETTE[factor] ?? "#6B7280",
        }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Model Weights</h1>
          <p className="text-sm text-gray-500 mt-1">
            Signal aggregation weights for stock agents and crypto factors
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>
            Source:{" "}
            <span className="text-gray-300 font-medium">{data.source}</span>
          </span>
          <span className="text-gray-700">|</span>
          <span>
            Samples:{" "}
            <span className="text-gray-300 font-medium">
              {data.sample_size}
            </span>
          </span>
        </div>
      </div>

      {/* Threshold pills */}
      <div className="flex gap-3">
        <div className="inline-flex items-center gap-2 rounded-full bg-green-500/10 border border-green-500/20 px-4 py-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
          <span className="text-xs text-green-400/80">Buy Threshold</span>
          <span className="text-sm font-mono font-semibold text-green-300">
            {data.buy_threshold.toFixed(2)}
          </span>
        </div>
        <div className="inline-flex items-center gap-2 rounded-full bg-red-500/10 border border-red-500/20 px-4 py-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
          <span className="text-xs text-red-400/80">Sell Threshold</span>
          <span className="text-sm font-mono font-semibold text-red-300">
            {data.sell_threshold.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Stock Weights */}
        {stockWeights && (
          <Card padding="lg">
            <CardBody className="p-0">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-5 rounded-full bg-accent" />
                <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
                  Stock Agents
                </h2>
                <span className="text-[10px] text-gray-600 ml-auto">
                  3 agents
                </span>
              </div>

              <div className="flex items-center gap-6">
                <div className="shrink-0">
                  <DonutChart segments={stockSegments} size={160} stroke={20} />
                </div>
                <div className="flex-1 min-w-0">
                  {stockSegments.map((seg) => (
                    <WeightRow
                      key={seg.label}
                      color={seg.color}
                      label={agentShortName(seg.label)}
                      pct={seg.value}
                      description={AGENT_DESCRIPTIONS[seg.label]}
                    />
                  ))}
                </div>
              </div>
            </CardBody>
          </Card>
        )}

        {/* Crypto Factor Weights */}
        {cryptoSegments.length > 0 && (
          <Card padding="lg">
            <CardBody className="p-0">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-1 h-5 rounded-full bg-violet-500" />
                <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
                  Crypto Factors
                </h2>
                <span className="text-[10px] text-gray-600 ml-auto">
                  7-factor model &middot; BTC &amp; ETH
                </span>
              </div>

              <div className="flex items-center gap-6">
                <div className="shrink-0">
                  <DonutChart segments={cryptoSegments} size={160} stroke={20} />
                </div>
                <div className="flex-1 min-w-0">
                  {cryptoSegments.map((seg) => (
                    <WeightRow
                      key={seg.label}
                      color={seg.color}
                      label={formatFactorName(seg.label)}
                      pct={seg.value}
                      description={FACTOR_DESCRIPTIONS[seg.label]}
                    />
                  ))}
                </div>
              </div>
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
