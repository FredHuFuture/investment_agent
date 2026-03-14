import { useMemo } from "react";
import {
  ComposedChart,
  AreaChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
} from "recharts";
import { formatCurrency } from "../../lib/formatters";
import type { SignalLogEntry } from "../../api/types";

// ---------------------------------------------------------------------------
// Custom triangle dot for signal markers
// ---------------------------------------------------------------------------
interface DotProps {
  cx?: number;
  cy?: number;
  payload?: ChartPoint;
}

function SignalDot(props: DotProps) {
  const { cx, cy, payload } = props;
  if (!cx || !cy || !payload?.signal || payload.signal === "HOLD") return null;
  const isBuy = payload.signal === "BUY";
  const size = 7;

  const path = isBuy
    ? `M ${cx} ${cy - size} L ${cx - size} ${cy + size} L ${cx + size} ${cy + size} Z`
    : `M ${cx} ${cy + size} L ${cx - size} ${cy - size} L ${cx + size} ${cy - size} Z`;

  return (
    <path
      d={path}
      fill={isBuy ? "#00CC66" : "#CC3333"}
      stroke={isBuy ? "#00994D" : "#991F1F"}
      strokeWidth={1}
    />
  );
}

// ---------------------------------------------------------------------------
// Tooltip components
// ---------------------------------------------------------------------------
interface EquityTTProps {
  active?: boolean;
  payload?: Array<{ payload: ChartPoint }>;
  label?: string;
}

function EquityTooltip({ active, payload, label }: EquityTTProps) {
  if (!active || !payload?.length) return null;
  const first = payload[0];
  if (!first) return null;
  const point = first.payload;
  const date = new Date(label ?? point.date).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="bg-gray-950/95 border border-gray-700/60 rounded px-2.5 py-1.5 text-[11px] shadow-2xl backdrop-blur-sm">
      <div className="text-gray-500">{date}</div>
      <div className="text-blue-400 font-semibold font-mono mt-0.5">
        {formatCurrency(point.equity)}
      </div>
      {point.drawdownPct !== undefined && point.drawdownPct < 0 && (
        <div className="text-red-400 text-[10px]">
          DD: {(point.drawdownPct * 100).toFixed(1)}%
        </div>
      )}
      {point.signal && point.signal !== "HOLD" && (
        <div className="mt-1 pt-1 border-t border-gray-800">
          <span
            className={`font-bold ${point.signal === "BUY" ? "text-green-400" : "text-red-400"}`}
          >
            {point.signal}
          </span>
          <span className="text-gray-500 ml-2">
            {point.confidence?.toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  );
}

interface PriceTTProps {
  active?: boolean;
  payload?: Array<{ value: number; payload: ChartPoint }>;
  label?: string;
}

function PriceTooltip({ active, payload, label }: PriceTTProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  if (!point || point.value == null) return null;
  const date = new Date(label ?? "").toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  return (
    <div className="bg-gray-950/95 border border-gray-700/60 rounded px-2.5 py-1.5 text-[11px] shadow-2xl backdrop-blur-sm">
      <div className="text-gray-500">{date}</div>
      <div className="text-white font-semibold font-mono mt-0.5">
        {formatCurrency(point.value)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface ChartPoint {
  date: string;
  equity: number;
  price?: number;
  drawdownPct?: number;
  signal?: string;
  confidence?: number;
  rawScore?: number;
  signalEquity?: number;
}

interface Props {
  data: Array<{ date: string; equity: number; price?: number }>;
  signalsLog?: SignalLogEntry[];
  initialCapital?: number;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function EquityCurveChart({
  data,
  signalsLog = [],
  initialCapital = 100000,
}: Props) {
  const computed = useMemo(() => {
    if (data.length === 0) return null;

    const hasPrice = data.some((d) => d.price != null);

    let peak = 0;
    const withDrawdown: ChartPoint[] = data.map((d) => {
      peak = Math.max(peak, d.equity);
      const dd = peak > 0 ? (d.equity - peak) / peak : 0;
      return { date: d.date, equity: d.equity, price: d.price, drawdownPct: dd };
    });

    const signalMap = new Map<
      string,
      { signal: string; confidence: number; rawScore: number }
    >();
    let totalBuySell = 0;

    for (const s of signalsLog) {
      if (s.signal === "HOLD") continue;
      totalBuySell++;
      signalMap.set(s.date, {
        signal: s.signal,
        confidence: s.confidence,
        rawScore: s.raw_score,
      });
    }

    const chartData: ChartPoint[] = withDrawdown.map((d) => {
      const sig = signalMap.get(d.date);
      if (sig) {
        return {
          ...d,
          signal: sig.signal,
          confidence: sig.confidence,
          rawScore: sig.rawScore,
          signalEquity: d.equity,
        };
      }
      return d;
    });

    // Equity domain
    const equities = chartData.map((d) => d.equity);
    const minEq = Math.min(...equities);
    const maxEq = Math.max(...equities);
    const eqPad = (maxEq - minEq) * 0.1 || maxEq * 0.05;
    const yDomain: [number, number] = [Math.max(0, minEq - eqPad), maxEq + eqPad];

    // Price domain + change
    let priceDomain: [number, number] = [0, 100];
    let priceIsUp = true;
    let priceChangePct = 0;
    let priceChangeAbs = 0;
    let priceFirst = 0;
    let priceLast = 0;

    if (hasPrice) {
      const prices = chartData.filter((d) => d.price != null).map((d) => d.price!);
      if (prices.length > 1) {
        const minP = Math.min(...prices);
        const maxP = Math.max(...prices);
        const pPad = (maxP - minP) * 0.06 || maxP * 0.03;
        priceDomain = [Math.max(0, minP - pPad), maxP + pPad];
        priceFirst = prices[0]!;
        priceLast = prices[prices.length - 1]!;
        priceIsUp = priceLast >= priceFirst;
        priceChangePct = priceFirst > 0 ? ((priceLast - priceFirst) / priceFirst) * 100 : 0;
        priceChangeAbs = priceLast - priceFirst;
      }
    }

    return {
      chartData,
      totalBuySell,
      yDomain,
      hasPrice,
      priceDomain,
      priceIsUp,
      priceChangePct,
      priceChangeAbs,
      priceLast,
    };
  }, [data, signalsLog]);

  if (!computed || data.length === 0) return null;

  const {
    chartData,
    totalBuySell,
    yDomain,
    hasPrice,
    priceDomain,
    priceIsUp,
    priceChangePct,
    priceChangeAbs,
    priceLast,
  } = computed;

  const priceLineColor = priceIsUp ? "#22c55e" : "#ef4444";
  const priceGradId = priceIsUp ? "btPriceGradUp" : "btPriceGradDown";

  return (
    <div className="space-y-5">
      {/* ── Equity Curve ── */}
      <div>
        <div className="text-[10px] text-gray-500 mb-2 uppercase tracking-wider font-medium">
          Portfolio Equity
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={chartData}
              margin={{ top: 4, right: 0, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.15} />
                  <stop offset="50%" stopColor="#60a5fa" stopOpacity={0.06} />
                  <stop offset="100%" stopColor="#60a5fa" stopOpacity={0} />
                </linearGradient>
              </defs>

              <XAxis
                dataKey="date"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#4b5563", fontSize: 10 }}
                tickFormatter={(v: string) =>
                  new Date(v).toLocaleDateString("en-US", {
                    month: "short",
                    year: "2-digit",
                  })
                }
                minTickGap={40}
              />

              <YAxis
                domain={yDomain}
                orientation="right"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#4b5563", fontSize: 10 }}
                tickFormatter={(v: number) =>
                  v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v.toFixed(0)}`
                }
                width={52}
              />

              <Tooltip
                content={<EquityTooltip />}
                cursor={{ stroke: "#6b7280", strokeWidth: 1, strokeDasharray: "2 2" }}
              />

              <ReferenceLine
                y={initialCapital}
                stroke="#374151"
                strokeDasharray="6 4"
              />

              <Area
                type="monotone"
                dataKey="equity"
                fill="url(#eqGrad)"
                stroke="none"
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="equity"
                stroke="#60a5fa"
                dot={false}
                strokeWidth={1.5}
                activeDot={{
                  r: 3,
                  fill: "#60a5fa",
                  stroke: "#111827",
                  strokeWidth: 2,
                }}
                isAnimationActive={false}
              />
              <Scatter
                dataKey="signalEquity"
                shape={<SignalDot />}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Equity legend */}
        <div className="mt-2 flex items-center gap-5 px-1">
          <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
            <span className="inline-block w-3 h-0.5 bg-blue-400 rounded" />
            Equity
          </span>
          {totalBuySell > 0 && (
            <>
              <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
                <span className="inline-block w-0 h-0 border-l-[4px] border-r-[4px] border-b-[7px] border-l-transparent border-r-transparent border-b-[#00CC66]" />
                BUY
              </span>
              <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
                <span className="inline-block w-0 h-0 border-l-[4px] border-r-[4px] border-t-[7px] border-l-transparent border-r-transparent border-t-[#CC3333]" />
                SELL
              </span>
            </>
          )}
          <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
            <span className="inline-block w-3 h-0.5 border-t border-dashed border-gray-600" />
            Initial
          </span>
          {totalBuySell > 0 && (
            <span className="text-[10px] text-gray-600 ml-auto">
              {totalBuySell} signals
            </span>
          )}
        </div>
      </div>

      {/* ── Asset Price Chart (Binance-style) ── */}
      {hasPrice && (
        <div>
          {/* Price header with change */}
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">
              Asset Price
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-semibold font-mono text-white">
                {formatCurrency(priceLast)}
              </span>
              <span
                className={`text-xs font-mono ${priceIsUp ? "text-green-400" : "text-red-400"}`}
              >
                {priceIsUp ? "+" : ""}
                {priceChangeAbs.toFixed(2)}
              </span>
              <span
                className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                  priceIsUp
                    ? "bg-green-500/15 text-green-400"
                    : "bg-red-500/15 text-red-400"
                }`}
              >
                {priceIsUp ? "+" : ""}
                {priceChangePct.toFixed(2)}%
              </span>
            </div>
          </div>

          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 4, right: 0, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id={priceGradId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={priceLineColor} stopOpacity={0.15} />
                    <stop offset="50%" stopColor={priceLineColor} stopOpacity={0.06} />
                    <stop offset="100%" stopColor={priceLineColor} stopOpacity={0} />
                  </linearGradient>
                </defs>

                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#4b5563", fontSize: 10 }}
                  tickFormatter={(v: string) =>
                    new Date(v).toLocaleDateString("en-US", {
                      month: "short",
                      year: "2-digit",
                    })
                  }
                  minTickGap={40}
                />

                <YAxis
                  domain={priceDomain}
                  orientation="right"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#4b5563", fontSize: 10 }}
                  tickFormatter={(v: number) =>
                    v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v.toFixed(0)}`
                  }
                  width={52}
                />

                <Tooltip
                  content={<PriceTooltip />}
                  cursor={{ stroke: "#6b7280", strokeWidth: 1, strokeDasharray: "2 2" }}
                />

                <Area
                  type="monotone"
                  dataKey="price"
                  stroke={priceLineColor}
                  strokeWidth={1.5}
                  fill={`url(#${priceGradId})`}
                  dot={false}
                  activeDot={{
                    r: 3,
                    fill: priceLineColor,
                    stroke: "#111827",
                    strokeWidth: 2,
                  }}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
