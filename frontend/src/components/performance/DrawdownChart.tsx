import { useApi } from "../../hooks/useApi";
import { getDrawdownSeries } from "../../api/endpoints";
import type { DrawdownPoint } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

export default function DrawdownChart() {
  const { data, loading, error, refetch } = useApi<DrawdownPoint[]>(
    () => getDrawdownSeries(90),
    { cacheKey: "perf:drawdown", ttlMs: 60_000 },
  );

  if (loading) return <SkeletonCard className="h-[340px]" />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  const series = data ?? [];

  return (
    <Card>
      <CardHeader title="Drawdown" subtitle="Peak-to-trough decline (90 days)" />
      <CardBody>
        {series.length === 0 ? (
          <EmptyState message="No portfolio snapshots yet." />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={series}>
              <defs>
                <linearGradient id="colorDrawdown" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f87171" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#f87171" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickFormatter={(v: string) => {
                  const d = new Date(v);
                  return `${d.getMonth() + 1}/${d.getDate()}`;
                }}
              />
              <YAxis
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                domain={["auto", 0]}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#111827",
                  border: "1px solid #374151",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number) => [`${value.toFixed(2)}%`, "Drawdown"]}
                labelFormatter={(v: string) => v}
              />
              <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />
              <Area
                type="monotone"
                dataKey="drawdown_pct"
                stroke="#f87171"
                fill="url(#colorDrawdown)"
                strokeWidth={2}
                name="Drawdown"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  );
}
