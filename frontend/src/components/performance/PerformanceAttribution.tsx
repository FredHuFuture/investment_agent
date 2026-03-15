import { useApi } from "../../hooks/useApi";
import { getPerformanceAttribution } from "../../api/endpoints";
import type { PerformanceAttribution as PerformanceAttributionType } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";
import { formatCurrency } from "../../lib/formatters";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";

interface AttributionTooltipProps {
  active?: boolean;
  payload?: Array<{
    payload: PerformanceAttributionType;
  }>;
}

function AttributionTooltip({ active, payload }: AttributionTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const first = payload[0];
  if (!first) return null;
  const d = first.payload;
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs shadow-lg">
      <p className="font-semibold text-white mb-1">{d.ticker}</p>
      <p className="text-gray-400">
        P&L:{" "}
        <span className={d.pnl >= 0 ? "text-green-400" : "text-red-400"}>
          {d.pnl >= 0 ? "+" : ""}
          {formatCurrency(d.pnl)}
        </span>
      </p>
      <p className="text-gray-400">
        P&L %:{" "}
        <span className={d.pnl_pct >= 0 ? "text-green-400" : "text-red-400"}>
          {d.pnl_pct >= 0 ? "+" : ""}
          {d.pnl_pct.toFixed(2)}%
        </span>
      </p>
      <p className="text-gray-400">
        Contribution:{" "}
        <span className={d.contribution_pct >= 0 ? "text-green-400" : "text-red-400"}>
          {d.contribution_pct >= 0 ? "+" : ""}
          {d.contribution_pct.toFixed(2)}%
        </span>
      </p>
    </div>
  );
}

export default function PerformanceAttribution() {
  const { data, loading, error, refetch } = useApi<PerformanceAttributionType[]>(
    () => getPerformanceAttribution(),
    { cacheKey: "perf:attribution", ttlMs: 60_000 },
  );

  if (loading) return <SkeletonCard className="h-[440px]" />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  const entries = data ?? [];

  return (
    <Card>
      <CardHeader title="P&L Attribution" subtitle="Per-position contribution to total P&L" />
      <CardBody>
        {entries.length === 0 ? (
          <EmptyState message="No positions to attribute." />
        ) : (
          <>
            {/* Horizontal bar chart */}
            <ResponsiveContainer width="100%" height={Math.max(250, entries.length * 36)}>
              <BarChart
                data={entries}
                layout="vertical"
                margin={{ top: 5, right: 30, bottom: 5, left: 60 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  tickFormatter={(v: number) => `${v.toFixed(0)}%`}
                />
                <YAxis
                  type="category"
                  dataKey="ticker"
                  tick={{ fill: "#d1d5db", fontSize: 11 }}
                  width={55}
                />
                <Tooltip
                  content={<AttributionTooltip />}
                  cursor={{ fill: "rgba(255,255,255,0.05)" }}
                />
                <ReferenceLine x={0} stroke="#4b5563" />
                <Bar dataKey="contribution_pct" radius={[0, 4, 4, 0]} name="Contribution">
                  {entries.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.contribution_pct >= 0 ? "#10b981" : "#ef4444"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            {/* Summary table */}
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800/50">
                    <th className="text-left py-2 pr-4">Ticker</th>
                    <th className="text-left py-2 px-4">Sector</th>
                    <th className="text-right py-2 px-4">P&L</th>
                    <th className="text-right py-2 px-4">P&L %</th>
                    <th className="text-right py-2 pl-4">Contribution %</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr
                      key={e.ticker}
                      className="border-b border-gray-800/30 last:border-0"
                    >
                      <td className="py-2 pr-4 font-mono text-white font-medium">
                        {e.ticker}
                        {e.status === "closed" && (
                          <span className="ml-1.5 text-[10px] text-gray-500 font-sans">closed</span>
                        )}
                      </td>
                      <td className="py-2 px-4 text-gray-400">{e.sector ?? "--"}</td>
                      <td
                        className={`py-2 px-4 text-right font-medium ${
                          e.pnl >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {e.pnl >= 0 ? "+" : ""}
                        {formatCurrency(e.pnl)}
                      </td>
                      <td
                        className={`py-2 px-4 text-right ${
                          e.pnl_pct >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {e.pnl_pct >= 0 ? "+" : ""}
                        {e.pnl_pct.toFixed(2)}%
                      </td>
                      <td
                        className={`py-2 pl-4 text-right font-medium ${
                          e.contribution_pct >= 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {e.contribution_pct >= 0 ? "+" : ""}
                        {e.contribution_pct.toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
