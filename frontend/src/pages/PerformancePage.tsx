import { useApi } from "../hooks/useApi";
import {
  getValueHistory,
  getPerformanceSummary,
  getMonthlyReturns,
  getTopPerformers,
} from "../api/endpoints";
import type {
  ValueHistoryPoint,
  PerformanceSummary,
  MonthlyReturn,
  TopPerformers,
} from "../api/types";
import MetricCard from "../components/shared/MetricCard";
import { Card, CardHeader, CardBody } from "../components/ui/Card";
import { SkeletonCard, SkeletonTable } from "../components/ui/Skeleton";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import WarningsBanner from "../components/shared/WarningsBanner";
import { formatCurrency, formatDate } from "../lib/formatters";
import { usePageTitle } from "../hooks/usePageTitle";
import {
  AreaChart,
  Area,
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

export default function PerformancePage() {
  usePageTitle("Performance");
  const valueHistory = useApi<ValueHistoryPoint[]>(
    () => getValueHistory(90),
    { cacheKey: "perf:valueHistory", ttlMs: 60_000 },
  );
  const perfSummary = useApi<PerformanceSummary>(
    () => getPerformanceSummary(),
    { cacheKey: "perf:summary", ttlMs: 60_000 },
  );
  const monthlyReturns = useApi<MonthlyReturn[]>(
    () => getMonthlyReturns(),
    { cacheKey: "perf:monthly", ttlMs: 120_000 },
  );
  const topPerformers = useApi<TopPerformers>(
    () => getTopPerformers(5),
    { cacheKey: "perf:topPerformers", ttlMs: 120_000 },
  );

  const loading =
    valueHistory.loading ||
    perfSummary.loading ||
    monthlyReturns.loading ||
    topPerformers.loading;
  const error =
    valueHistory.error ||
    perfSummary.error ||
    monthlyReturns.error ||
    topPerformers.error;
  const warnings = [
    ...valueHistory.warnings,
    ...perfSummary.warnings,
    ...monthlyReturns.warnings,
    ...topPerformers.warnings,
  ];

  if (loading)
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Performance</h1>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {Array.from({ length: 5 }, (_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        <SkeletonCard className="h-[340px]" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SkeletonCard className="h-[340px]" />
          <SkeletonTable rows={8} columns={4} />
        </div>
      </div>
    );

  if (error) return <ErrorAlert message={error} />;

  const perf = perfSummary.data;
  const history = valueHistory.data ?? [];
  const monthly = monthlyReturns.data ?? [];
  const top = topPerformers.data;

  const pnlTrend = perf && perf.total_realized_pnl >= 0 ? "up" : "down";
  const pnlSign = perf && perf.total_realized_pnl >= 0 ? "+" : "";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Performance</h1>
      <WarningsBanner warnings={warnings} />

      {/* Key metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <MetricCard
          label="Total P&L"
          value={`${pnlSign}${formatCurrency(perf?.total_realized_pnl ?? 0)}`}
          sub={`${perf?.total_trades ?? 0} trades`}
          trend={pnlTrend}
        />
        <MetricCard
          label="Win Rate"
          value={`${(perf?.win_rate ?? 0).toFixed(1)}%`}
          sub={`${perf?.win_count ?? 0}W / ${perf?.loss_count ?? 0}L`}
          trend={
            perf && perf.win_rate >= 50
              ? "up"
              : perf && perf.win_rate > 0
                ? "down"
                : undefined
          }
        />
        <MetricCard
          label="Avg Win"
          value={`+${(perf?.avg_win_pct ?? 0).toFixed(1)}%`}
          trend="up"
        />
        <MetricCard
          label="Avg Loss"
          value={`${(perf?.avg_loss_pct ?? 0).toFixed(1)}%`}
          trend="down"
        />
        <MetricCard
          label="Total Trades"
          value={String(perf?.total_trades ?? 0)}
          sub={`${(perf?.avg_hold_days ?? 0).toFixed(0)}d avg hold`}
        />
      </div>

      {/* Portfolio value chart */}
      <Card>
        <CardHeader title="Portfolio Value (90 days)" />
        <CardBody>
          {history.length === 0 ? (
            <EmptyState message="No snapshots yet. Run a health check to generate data." />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={history}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  tickFormatter={(v) => {
                    const d = new Date(v);
                    return `${d.getMonth() + 1}/${d.getDate()}`;
                  }}
                />
                <YAxis
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  tickFormatter={(v) =>
                    `$${(v / 1000).toFixed(0)}k`
                  }
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#111827",
                    border: "1px solid #374151",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  labelFormatter={(v) => formatDate(String(v))}
                  formatter={(value: number) => [formatCurrency(value), ""]}
                />
                <Area
                  type="monotone"
                  dataKey="total_value"
                  stroke="#3b82f6"
                  fill="url(#colorValue)"
                  strokeWidth={2}
                  name="Total Value"
                />
                <Area
                  type="monotone"
                  dataKey="invested"
                  stroke="#10b981"
                  fill="none"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  name="Invested"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardBody>
      </Card>

      {/* Monthly returns + Top performers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly returns bar chart */}
        <Card>
          <CardHeader title="Monthly Returns" />
          <CardBody>
            {monthly.length === 0 ? (
              <EmptyState message="No closed trades yet." />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={monthly}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis
                    dataKey="month"
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                  />
                  <YAxis
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    tickFormatter={(v) => `$${v.toLocaleString()}`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#111827",
                      border: "1px solid #374151",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={(value: number) => [formatCurrency(value), "P&L"]}
                  />
                  <ReferenceLine y={0} stroke="#4b5563" />
                  <Bar dataKey="pnl" radius={[4, 4, 0, 0]} name="P&L">
                    {monthly.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.pnl >= 0 ? "#10b981" : "#ef4444"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        {/* Top performers table */}
        <Card>
          <CardHeader title="Top Performers" />
          <CardBody>
            {!top ||
            (top.best.length === 0 && top.worst.length === 0) ? (
              <EmptyState message="No closed trades yet." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800/50">
                      <th className="text-left py-2 pr-4">Ticker</th>
                      <th className="text-right py-2 px-4">Return</th>
                      <th className="text-right py-2 px-4">P&L</th>
                      <th className="text-right py-2 pl-4">Exit Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {top.best.map((t) => (
                      <tr
                        key={`best-${t.ticker}-${t.exit_date}`}
                        className="border-b border-gray-800/30 last:border-0"
                      >
                        <td className="py-2 pr-4 font-mono text-white font-medium">
                          {t.ticker}
                        </td>
                        <td className="py-2 px-4 text-right text-green-400 font-medium">
                          +{t.return_pct.toFixed(1)}%
                        </td>
                        <td className="py-2 px-4 text-right text-green-400">
                          +{formatCurrency(t.pnl)}
                        </td>
                        <td className="py-2 pl-4 text-right text-gray-400">
                          {t.exit_date ? formatDate(t.exit_date) : "-"}
                        </td>
                      </tr>
                    ))}
                    {top.best.length > 0 && top.worst.length > 0 && (
                      <tr>
                        <td
                          colSpan={4}
                          className="py-1 border-b border-gray-700/50"
                        />
                      </tr>
                    )}
                    {top.worst.map((t) => (
                      <tr
                        key={`worst-${t.ticker}-${t.exit_date}`}
                        className="border-b border-gray-800/30 last:border-0"
                      >
                        <td className="py-2 pr-4 font-mono text-white font-medium">
                          {t.ticker}
                        </td>
                        <td className="py-2 px-4 text-right text-red-400 font-medium">
                          {t.return_pct.toFixed(1)}%
                        </td>
                        <td className="py-2 px-4 text-right text-red-400">
                          {formatCurrency(t.pnl)}
                        </td>
                        <td className="py-2 pl-4 text-right text-gray-400">
                          {t.exit_date ? formatDate(t.exit_date) : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
