import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useApi } from "../../hooks/useApi";
import { getAccuracyTrend } from "../../api/endpoints";
import type { SignalAccuracyTrendPoint } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonTable } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";

interface TrendTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: SignalAccuracyTrendPoint }>;
  label?: string;
}

function TrendTooltip({ active, payload }: TrendTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  if (!point) return null;

  const dateStr = new Date(point.date + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="bg-gray-950/95 border border-gray-700/60 rounded px-2.5 py-1.5 text-[11px] shadow-2xl backdrop-blur-sm">
      <div className="text-gray-500">{dateStr}</div>
      <div className="text-accent-light font-semibold font-mono mt-0.5">
        {point.accuracy_pct.toFixed(1)}%
      </div>
      <div className="text-gray-500 text-[10px] mt-0.5">
        Sample: {point.sample_size}
      </div>
    </div>
  );
}

export default function AccuracyTrendChart() {
  const { data, loading, error, refetch } = useApi<SignalAccuracyTrendPoint[]>(
    () => getAccuracyTrend(),
    [],
    { cacheKey: "signals:accuracy-trend", ttlMs: 60_000 },
  );

  return (
    <Card>
      <CardHeader title="Signal Accuracy Trend" subtitle="Rolling window accuracy over resolved signals" />
      <CardBody>
        {loading && <SkeletonTable rows={4} columns={3} />}
        {error && <ErrorAlert message={error} onRetry={refetch} />}
        {!loading && !error && (!data || data.length === 0) && (
          <EmptyState
            message="Not enough resolved signals for accuracy trend."
            hint="Accuracy trend requires enough resolved signals to fill the rolling window."
          />
        )}
        {!loading && !error && data && data.length > 0 && (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data}
                margin={{ top: 4, right: 0, left: 0, bottom: 0 }}
              >
                <XAxis
                  dataKey="date"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#4b5563", fontSize: 10 }}
                  tickFormatter={(v: string) => {
                    const d = new Date(v + "T00:00:00");
                    return d.toLocaleDateString("en-US", {
                      month: "numeric",
                      day: "numeric",
                    });
                  }}
                  minTickGap={40}
                />
                <YAxis
                  domain={[0, 100]}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#4b5563", fontSize: 10 }}
                  tickFormatter={(v: number) => `${v}%`}
                  width={42}
                />
                <Tooltip content={<TrendTooltip />} cursor={{ stroke: "#736e66", strokeWidth: 1, strokeDasharray: "2 2" }} />
                <ReferenceLine
                  y={50}
                  stroke="#4b5563"
                  strokeDasharray="3 3"
                  label={{
                    value: "Random",
                    position: "right",
                    fill: "#4b5563",
                    fontSize: 10,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="accuracy_pct"
                  stroke="#32af78"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{
                    r: 3,
                    fill: "#32af78",
                    stroke: "#111827",
                    strokeWidth: 2,
                  }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
