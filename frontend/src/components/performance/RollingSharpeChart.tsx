import { useApi } from "../../hooks/useApi";
import { getRollingSharpe } from "../../api/endpoints";
import type { RollingSharpePoint } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

export default function RollingSharpeChart() {
  const { data, loading, error, refetch } = useApi<RollingSharpePoint[]>(
    () => getRollingSharpe(90, 30),
    { cacheKey: "perf:rollingSharpe", ttlMs: 60_000 },
  );

  if (loading) return <SkeletonCard className="h-[340px]" />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  const series = data ?? [];

  return (
    <Card>
      <CardHeader title="Rolling Sharpe Ratio" subtitle="30-day window, annualised" />
      <CardBody>
        {series.length === 0 ? (
          <EmptyState message="Not enough data for rolling Sharpe calculation." />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={series}>
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
                tickFormatter={(v: number) => v.toFixed(1)}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#111827",
                  border: "1px solid #374151",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number) => [value.toFixed(2), "Sharpe"]}
                labelFormatter={(v: string) => v}
              />
              <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" label={{ value: "0", fill: "#6b7280", fontSize: 10 }} />
              <ReferenceLine y={1} stroke="#374151" strokeDasharray="3 3" label={{ value: "1.0", fill: "#6b7280", fontSize: 10 }} />
              <ReferenceLine y={2} stroke="#374151" strokeDasharray="3 3" label={{ value: "2.0", fill: "#6b7280", fontSize: 10 }} />
              <Line
                type="monotone"
                dataKey="sharpe"
                stroke="#60a5fa"
                strokeWidth={2}
                dot={false}
                name="Sharpe"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  );
}
