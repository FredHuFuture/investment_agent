import { useApi } from "../../hooks/useApi";
import { getAlertTimeline } from "../../api/endpoints";
import type { AlertTimelinePoint } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "#f87171", // red-400
  HIGH: "#fb923c",     // orange-400
  WARNING: "#facc15",  // yellow-400
  MEDIUM: "#facc15",   // yellow-400
  LOW: "#94a3b8",      // gray-400
  INFO: "#60a5fa",     // blue-400
};

/** All possible severity keys to render as stacked bars. */
const SEVERITY_KEYS = ["CRITICAL", "HIGH", "WARNING", "MEDIUM", "LOW", "INFO"];

/**
 * Transform timeline data into flat records for recharts stacked bar chart.
 * Each record: { date, CRITICAL: N, HIGH: N, ... }
 */
function flattenTimeline(
  points: AlertTimelinePoint[],
): Array<Record<string, string | number>> {
  return points.map((p) => {
    const row: Record<string, string | number> = { date: p.date };
    for (const key of SEVERITY_KEYS) {
      row[key] = p.severity_breakdown[key] ?? 0;
    }
    return row;
  });
}

export default function AlertTimeline() {
  const { data, loading, error, refetch } = useApi<AlertTimelinePoint[]>(
    () => getAlertTimeline(30),
    { cacheKey: "monitoring:alertTimeline", ttlMs: 60_000 },
  );

  if (loading) return <SkeletonCard />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;
  if (!data || data.length === 0) return null;

  const chartData = flattenTimeline(data);

  // Determine which severity keys actually have data
  const activeSeverities = SEVERITY_KEYS.filter((key) =>
    chartData.some((row) => (row[key] as number) > 0),
  );

  return (
    <Card>
      <CardHeader title="Alert Timeline" subtitle="Last 30 days" />
      <CardBody>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#9ca3af", fontSize: 11 }}
                tickFormatter={(v: string) => v.slice(5)} // "MM-DD"
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: "#9ca3af", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1f2937",
                  border: "1px solid #374151",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#d1d5db" }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, color: "#9ca3af" }}
              />
              {activeSeverities.map((key) => (
                <Bar
                  key={key}
                  dataKey={key}
                  stackId="severity"
                  fill={SEVERITY_COLORS[key] ?? "#6b7280"}
                  name={key}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardBody>
    </Card>
  );
}
