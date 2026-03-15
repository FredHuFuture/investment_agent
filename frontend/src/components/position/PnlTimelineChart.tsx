import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { PositionPnlPoint } from "../../api/types";
import { Card, CardHeader, CardBody } from "../../components/ui/Card";
import { formatCurrency, formatDate } from "../../lib/formatters";

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------
interface PnlTTProps {
  active?: boolean;
  payload?: Array<{
    value: number;
    payload: PositionPnlPoint;
  }>;
}

function PnlTooltip({ active, payload }: PnlTTProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  if (!point) return null;
  const d = point.payload;
  return (
    <div className="bg-gray-950/95 border border-gray-700/60 rounded px-2.5 py-1.5 text-[11px] shadow-2xl backdrop-blur-sm">
      <div className="text-gray-500">{formatDate(d.date)}</div>
      <div className="flex justify-between gap-4 mt-0.5">
        <span className="text-gray-500">Price</span>
        <span className="text-white font-mono">{formatCurrency(d.price)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-gray-500">Cost Basis</span>
        <span className="text-white font-mono">
          {formatCurrency(d.cost_basis)}
        </span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-gray-500">P&L</span>
        <span
          className={`font-mono font-semibold ${
            d.unrealized_pnl >= 0 ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {d.unrealized_pnl >= 0 ? "+" : ""}
          {formatCurrency(d.unrealized_pnl)}
        </span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-gray-500">P&L %</span>
        <span
          className={`font-mono font-semibold ${
            d.unrealized_pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {d.unrealized_pnl_pct >= 0 ? "+" : ""}
          {(d.unrealized_pnl_pct * 100).toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart
// ---------------------------------------------------------------------------
interface PnlTimelineChartProps {
  data: PositionPnlPoint[];
}

export default function PnlTimelineChart({ data }: PnlTimelineChartProps) {
  // Determine if the latest P&L is positive or negative for default coloring
  const lastPoint = data[data.length - 1];
  const isPositive = lastPoint ? lastPoint.unrealized_pnl >= 0 : true;

  return (
    <Card>
      <CardHeader title="P&L Timeline" />
      <CardBody>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={data}
              margin={{ top: 4, right: 0, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="pnlGreen" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="pnlRed" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity={0.02} />
                  <stop offset="100%" stopColor="#ef4444" stopOpacity={0.3} />
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
                    day: "numeric",
                  })
                }
                minTickGap={40}
              />
              <YAxis
                orientation="right"
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#4b5563", fontSize: 10 }}
                tickFormatter={(v: number) =>
                  v >= 1000 || v <= -1000
                    ? `$${(v / 1000).toFixed(1)}k`
                    : `$${v.toFixed(0)}`
                }
                width={52}
              />
              <Tooltip
                content={<PnlTooltip />}
                cursor={{
                  stroke: "#6b7280",
                  strokeWidth: 1,
                  strokeDasharray: "2 2",
                }}
              />

              <ReferenceLine
                y={0}
                stroke="#4b5563"
                strokeDasharray="4 4"
              />

              <Area
                type="monotone"
                dataKey="unrealized_pnl"
                stroke={isPositive ? "#22c55e" : "#ef4444"}
                strokeWidth={1.5}
                fill={isPositive ? "url(#pnlGreen)" : "url(#pnlRed)"}
                dot={false}
                activeDot={{
                  r: 3,
                  fill: isPositive ? "#22c55e" : "#ef4444",
                  stroke: "#111827",
                  strokeWidth: 2,
                }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardBody>
    </Card>
  );
}
