import { useApi } from "../../hooks/useApi";
import { getAlertStats } from "../../api/endpoints";
import type { AlertStats } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import MetricCard from "../shared/MetricCard";
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
} from "recharts";

const SEVERITY_DOT_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-400",
  HIGH: "bg-orange-400",
  WARNING: "bg-yellow-400",
  MEDIUM: "bg-yellow-400",
  LOW: "bg-gray-400",
  INFO: "bg-blue-400",
};

/** Ordering so critical appears first in the severity list. */
const SEVERITY_ORDER = ["CRITICAL", "HIGH", "WARNING", "MEDIUM", "LOW", "INFO"];

function sortedSeverityEntries(
  map: Record<string, number>,
): Array<[string, number]> {
  return Object.entries(map).sort(
    (a, b) =>
      (SEVERITY_ORDER.indexOf(a[0]) === -1 ? 99 : SEVERITY_ORDER.indexOf(a[0])) -
      (SEVERITY_ORDER.indexOf(b[0]) === -1 ? 99 : SEVERITY_ORDER.indexOf(b[0])),
  );
}

export default function AlertAnalyticsPanel() {
  const { data, loading, error, refetch } = useApi<AlertStats>(
    () => getAlertStats(30),
    { cacheKey: "monitoring:alertStats", ttlMs: 30_000 },
  );

  if (loading) return <SkeletonCard />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;
  if (!data) return null;

  return (
    <Card>
      <CardHeader title="Alert Analytics" subtitle="Last 30 days" />
      <CardBody>
        {/* Top metric cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <MetricCard
            label="Total Alerts"
            value={String(data.total_count)}
          />
          <MetricCard
            label="Unacknowledged"
            value={String(data.unacknowledged_count)}
            className={data.unacknowledged_count > 0 ? "text-red-400" : undefined}
          />
          <MetricCard
            label="Ack Rate"
            value={`${data.ack_rate_pct.toFixed(1)}%`}
          />
          <MetricCard
            label="Daily Average"
            value={data.avg_alerts_per_day.toFixed(1)}
          />
        </div>

        {/* Most Alerted Tickers — horizontal bar chart */}
        {data.by_ticker.length > 0 && (
          <div className="mb-6">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
              Most Alerted Tickers
            </h4>
            <div style={{ height: Math.max(data.by_ticker.length * 36, 120) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.by_ticker}
                  layout="vertical"
                  margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={{ fill: "#9ca3af", fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="ticker"
                    width={70}
                    tick={{ fill: "#d1d5db", fontSize: 12, fontFamily: "monospace" }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1f2937",
                      border: "1px solid #374151",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "#d1d5db" }}
                    formatter={(value: number) => [value, "Alerts"]}
                  />
                  <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={20} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Distribution: severity + type */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* By Severity */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
              By Severity
            </h4>
            <ul className="space-y-2">
              {sortedSeverityEntries(data.by_severity).map(([sev, count]) => (
                <li key={sev} className="flex items-center justify-between text-sm text-gray-300">
                  <span className="flex items-center gap-2">
                    <span
                      className={`inline-block h-2.5 w-2.5 rounded-full ${SEVERITY_DOT_COLORS[sev] ?? "bg-gray-600"}`}
                    />
                    {sev}
                  </span>
                  <span className="font-mono text-gray-400">{count}</span>
                </li>
              ))}
              {Object.keys(data.by_severity).length === 0 && (
                <li className="text-xs text-gray-600">No data</li>
              )}
            </ul>
          </div>

          {/* By Type */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">
              By Type
            </h4>
            <ul className="space-y-2">
              {Object.entries(data.by_type)
                .sort((a, b) => b[1] - a[1])
                .map(([type, count]) => (
                  <li key={type} className="flex items-center justify-between text-sm text-gray-300">
                    <span className="truncate mr-2">
                      {type
                        .split("_")
                        .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
                        .join(" ")}
                    </span>
                    <span className="font-mono text-gray-400 shrink-0">{count}</span>
                  </li>
                ))}
              {Object.keys(data.by_type).length === 0 && (
                <li className="text-xs text-gray-600">No data</li>
              )}
            </ul>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
