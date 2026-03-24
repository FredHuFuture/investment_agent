import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useApi } from "../../hooks/useApi";
import { getRegimeHistory } from "../../api/endpoints";
import type { RegimeHistoryPoint } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import EmptyState from "../shared/EmptyState";

const REGIME_COLORS: Record<string, string> = {
  bull_market: "#22c55e",
  bear_market: "#ef4444",
  sideways: "#eab308",
  high_volatility: "#f97316",
  risk_off: "#a855f7",
};

const REGIME_LABELS: Record<string, string> = {
  bull_market: "Bull Market",
  bear_market: "Bear Market",
  sideways: "Sideways",
  high_volatility: "High Volatility",
  risk_off: "Risk Off",
};

function getRegimeColor(regime: string): string {
  return REGIME_COLORS[regime] ?? "#6b7280";
}

function getRegimeLabel(regime: string): string {
  return REGIME_LABELS[regime] ?? regime;
}

interface ChartDatum {
  label: string;
  regime: string;
  duration: number;
  confidence: number;
  date: string;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ChartDatum }>;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const first = payload[0];
  if (!first) return null;
  const d = first.payload;
  return (
    <div className="rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-white mb-1">{getRegimeLabel(d.regime)}</p>
      <p className="text-gray-400">
        Confidence: <span className="text-gray-200">{d.confidence.toFixed(0)}%</span>
      </p>
      <p className="text-gray-400">
        Duration: <span className="text-gray-200">{d.duration}d</span>
      </p>
      <p className="text-gray-400">
        Started: <span className="text-gray-200">{new Date(d.date).toLocaleDateString()}</span>
      </p>
    </div>
  );
}

export default function RegimeTimeline() {
  const { data, loading, error, refetch } = useApi<RegimeHistoryPoint[]>(
    () => getRegimeHistory(90),
    { cacheKey: "dashboard:regimeHistory", ttlMs: 120_000 },
  );

  const chartData: ChartDatum[] = useMemo(() => {
    if (!data || data.length === 0) return [];
    return data.map((pt) => ({
      label: new Date(pt.date).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      regime: pt.regime,
      duration: pt.duration_days,
      confidence: pt.confidence,
      date: pt.date,
    }));
  }, [data]);

  // Legend: unique regimes in the data
  const legendRegimes = useMemo(() => {
    if (!chartData.length) return [];
    const seen = new Set<string>();
    const result: string[] = [];
    for (const d of chartData) {
      if (!seen.has(d.regime)) {
        seen.add(d.regime);
        result.push(d.regime);
      }
    }
    return result;
  }, [chartData]);

  return (
    <Card>
      <CardHeader
        title="Market Regime History"
        subtitle="Last 90 days"
        action={
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            aria-label="Refresh regime history"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-4 h-4"
            >
              <path
                fillRule="evenodd"
                d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311V15.5a.75.75 0 0 1-1.5 0v-4a.75.75 0 0 1 .75-.75h4a.75.75 0 0 1 0 1.5H7.05l.243.242a4 4 0 0 0 6.695-1.793.75.75 0 0 1 1.324.725ZM4.688 8.576a5.5 5.5 0 0 1 9.201-2.466l.312.311V4.5a.75.75 0 0 1 1.5 0v4a.75.75 0 0 1-.75.75h-4a.75.75 0 0 1 0-1.5h1.999l-.243-.242a4 4 0 0 0-6.695 1.793.75.75 0 0 1-1.324-.725Z"
                clipRule="evenodd"
              />
            </svg>
          </Button>
        }
      />
      <CardBody>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-600 border-t-accent" />
          </div>
        ) : error ? (
          <p className="text-xs text-red-400">Failed to load regime history.</p>
        ) : chartData.length === 0 ? (
          <EmptyState message="No regime history recorded yet." />
        ) : (
          <>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartData}
                  margin={{ top: 4, right: 4, bottom: 0, left: 4 }}
                >
                  <XAxis
                    dataKey="label"
                    tick={{ fill: "#6b7280", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fill: "#6b7280", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    label={{
                      value: "Days",
                      angle: -90,
                      position: "insideLeft",
                      fill: "#6b7280",
                      fontSize: 10,
                    }}
                    width={40}
                  />
                  <Tooltip
                    content={<CustomTooltip />}
                    cursor={{ fill: "rgba(255,255,255,0.05)" }}
                  />
                  <Bar dataKey="duration" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={getRegimeColor(entry.regime)}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
              {legendRegimes.map((regime) => (
                <div
                  key={regime}
                  className="flex items-center gap-1.5 text-xs text-gray-400"
                >
                  <span
                    className="inline-block w-2.5 h-2.5 rounded-sm shrink-0"
                    style={{ backgroundColor: getRegimeColor(regime) }}
                  />
                  {getRegimeLabel(regime)}
                </div>
              ))}
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
