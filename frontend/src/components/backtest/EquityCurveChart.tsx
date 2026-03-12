import { useMemo } from "react";
import {
  ComposedChart,
  Line,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
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
// Custom tooltip
// ---------------------------------------------------------------------------
interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: ChartPoint }>;
  label?: string;
}

function ChartTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const first = payload[0];
  if (!first) return null;
  const point = first.payload;
  const date = new Date(label ?? point.date).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <div className="text-gray-400 mb-1">{date}</div>
      <div className="text-blue-400 font-semibold">
        Equity: {formatCurrency(point.equity)}
      </div>
      {point.price != null && (
        <div className="text-amber-400">
          Price: {formatCurrency(point.price)}
        </div>
      )}
      {point.drawdownPct !== undefined && point.drawdownPct < 0 && (
        <div className="text-red-400 text-[10px]">
          Drawdown: {(point.drawdownPct * 100).toFixed(1)}%
        </div>
      )}
      {point.signal && point.signal !== "HOLD" && (
        <div className="mt-1 pt-1 border-t border-gray-700">
          <span
            className={`font-bold ${point.signal === "BUY" ? "text-green-400" : "text-red-400"}`}
          >
            {point.signal}
          </span>
          <span className="text-gray-400 ml-2">
            {point.confidence?.toFixed(1)}% conf
          </span>
          {point.rawScore !== undefined && (
            <span className="text-gray-500 ml-2">
              score: {point.rawScore.toFixed(3)}
            </span>
          )}
        </div>
      )}
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
  const { chartData, totalBuySell, yDomain, priceDomain, hasPrice } = useMemo(() => {
    if (data.length === 0)
      return {
        chartData: [] as ChartPoint[],
        totalBuySell: 0,
        yDomain: [0, 100] as [number, number],
        priceDomain: [0, 100] as [number, number],
        hasPrice: false,
      };

    // Check if price data exists
    const priceAvail = data.some((d) => d.price != null);

    // Build equity lookup by date
    let peak = 0;
    const withDrawdown: ChartPoint[] = data.map((d) => {
      peak = Math.max(peak, d.equity);
      const dd = peak > 0 ? (d.equity - peak) / peak : 0;
      return { date: d.date, equity: d.equity, price: d.price, drawdownPct: dd };
    });

    // Build signal lookup
    const signalMap = new Map<
      string,
      { signal: string; confidence: number; rawScore: number }
    >();
    let totalBS = 0;

    for (const s of signalsLog) {
      if (s.signal === "HOLD") continue;
      totalBS++;
      signalMap.set(s.date, {
        signal: s.signal,
        confidence: s.confidence,
        rawScore: s.raw_score,
      });
    }

    // Merge signals into chart data
    const merged: ChartPoint[] = withDrawdown.map((d) => {
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

    // Compute Y domain with padding
    const equities = merged.map((d) => d.equity);
    const minEq = Math.min(...equities);
    const maxEq = Math.max(...equities);
    const padding = (maxEq - minEq) * 0.1 || maxEq * 0.05;
    const yMin = Math.max(0, minEq - padding);
    const yMax = maxEq + padding;

    // Compute price domain
    let pDomain: [number, number] = [0, 100];
    if (priceAvail) {
      const prices = merged.filter((d) => d.price != null).map((d) => d.price!);
      if (prices.length > 0) {
        const minP = Math.min(...prices);
        const maxP = Math.max(...prices);
        const pPad = (maxP - minP) * 0.1 || maxP * 0.05;
        pDomain = [Math.max(0, minP - pPad), maxP + pPad];
      }
    }

    return {
      chartData: merged,
      totalBuySell: totalBS,
      yDomain: [yMin, yMax] as [number, number],
      priceDomain: pDomain,
      hasPrice: priceAvail,
    };
  }, [data, signalsLog]);

  if (data.length === 0) return null;

  return (
    <div>
      {/* Chart */}
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            margin={{ top: 5, right: hasPrice ? 55 : 10, left: 10, bottom: 5 }}
          >
            <defs>
              <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#60a5fa" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#60a5fa" stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1f2937"
              vertical={false}
            />

            <XAxis
              dataKey="date"
              tick={{ fill: "#6b7280", fontSize: 10 }}
              tickFormatter={(v: string) =>
                new Date(v).toLocaleDateString("en-US", {
                  month: "short",
                  year: "2-digit",
                })
              }
              axisLine={{ stroke: "#374151" }}
              tickLine={false}
            />

            {/* Left Y-axis: Equity */}
            <YAxis
              yAxisId="equity"
              domain={yDomain}
              tick={{ fill: "#6b7280", fontSize: 10 }}
              tickFormatter={(v: number) =>
                v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v.toFixed(0)}`
              }
              axisLine={false}
              tickLine={false}
              width={55}
            />

            {/* Right Y-axis: Price (only if price data exists) */}
            {hasPrice && (
              <YAxis
                yAxisId="price"
                orientation="right"
                domain={priceDomain}
                tick={{ fill: "#92702a", fontSize: 10 }}
                tickFormatter={(v: number) =>
                  v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v.toFixed(0)}`
                }
                axisLine={false}
                tickLine={false}
                width={55}
              />
            )}

            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: "#4b5563", strokeDasharray: "3 3" }}
            />

            {/* Initial capital reference line */}
            <ReferenceLine
              yAxisId="equity"
              y={initialCapital}
              stroke="#4b5563"
              strokeDasharray="6 4"
            />

            {/* Equity area fill */}
            <Area
              yAxisId="equity"
              type="monotone"
              dataKey="equity"
              fill="url(#equityGrad)"
              stroke="none"
              isAnimationActive={false}
            />

            {/* Main equity line */}
            <Line
              yAxisId="equity"
              type="monotone"
              dataKey="equity"
              stroke="#60a5fa"
              dot={false}
              strokeWidth={2}
              activeDot={false}
              isAnimationActive={false}
            />

            {/* Price line (dashed amber) */}
            {hasPrice && (
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="price"
                stroke="#d4a24a"
                dot={false}
                strokeWidth={1.5}
                strokeDasharray="4 2"
                activeDot={false}
                isAnimationActive={false}
              />
            )}

            {/* Signal markers as scatter */}
            <Scatter
              yAxisId="equity"
              dataKey="signalEquity"
              shape={<SignalDot />}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="mt-3 flex items-center gap-5 px-2">
        <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
          <span className="inline-block w-3 h-0.5 bg-blue-400 rounded" />
          Equity
        </span>
        {hasPrice && (
          <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
            <span className="inline-block w-3 h-0.5 border-t border-dashed" style={{ borderColor: "#d4a24a" }} />
            Price
          </span>
        )}
        {totalBuySell > 0 && (
          <>
            <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
              <span className="inline-block w-0 h-0 border-l-[5px] border-r-[5px] border-b-[8px] border-l-transparent border-r-transparent border-b-[#00CC66]" />
              BUY
            </span>
            <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
              <span className="inline-block w-0 h-0 border-l-[5px] border-r-[5px] border-t-[8px] border-l-transparent border-r-transparent border-t-[#CC3333]" />
              SELL
            </span>
          </>
        )}
        <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
          <span className="inline-block w-3 h-0.5 border-t border-dashed border-gray-500" />
          Initial Capital
        </span>
        {totalBuySell > 0 && (
          <span className="text-[10px] text-gray-600 ml-auto">
            {totalBuySell} signals
          </span>
        )}
      </div>
    </div>
  );
}
