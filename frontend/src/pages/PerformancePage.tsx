import { useState } from "react";
import { useApi } from "../hooks/useApi";
import {
  getValueHistory,
  getPerformanceSummary,
  getMonthlyReturns,
  getTopPerformers,
  getBenchmarkComparison,
  getCumulativePnl,
} from "../api/endpoints";
import type {
  ValueHistoryPoint,
  PerformanceSummary,
  MonthlyReturn,
  TopPerformers,
  BenchmarkComparison,
  CumulativePnlPoint,
} from "../api/types";
import MetricCard from "../components/shared/MetricCard";
import { Card, CardHeader, CardBody } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SkeletonCard, SkeletonTable } from "../components/ui/Skeleton";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import WarningsBanner from "../components/shared/WarningsBanner";
import { formatCurrency, formatDate } from "../lib/formatters";
import { usePageTitle } from "../hooks/usePageTitle";
import DrawdownChart from "../components/performance/DrawdownChart";
import RollingSharpeChart from "../components/performance/RollingSharpeChart";
import MonthlyHeatmapCalendar from "../components/performance/MonthlyHeatmapCalendar";
import PerformanceAttribution from "../components/performance/PerformanceAttribution";
import SnapshotComparison from "../components/performance/SnapshotComparison";
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
  ComposedChart,
  Line,
} from "recharts";

export default function PerformancePage() {
  usePageTitle("Performance");
  const [monthlyMode, setMonthlyMode] = useState<"dollar" | "percent">("dollar");

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
  const benchmarkApi = useApi<BenchmarkComparison>(
    () => getBenchmarkComparison(90),
    { cacheKey: "perf:benchmark", ttlMs: 120_000 },
  );
  const cumulativePnlApi = useApi<CumulativePnlPoint[]>(
    () => getCumulativePnl(),
    { cacheKey: "perf:cumulativePnl", ttlMs: 120_000 },
  );

  function refetchAll() {
    valueHistory.refetch();
    perfSummary.refetch();
    monthlyReturns.refetch();
    topPerformers.refetch();
    benchmarkApi.refetch();
    cumulativePnlApi.refetch();
  }

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
    ...benchmarkApi.warnings,
    ...cumulativePnlApi.warnings,
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

  if (error) return <ErrorAlert message={error} onRetry={refetchAll} />;

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
        {benchmarkApi.data && (
          <MetricCard
            label={`Alpha vs ${benchmarkApi.data.benchmark_ticker}`}
            value={`${benchmarkApi.data.alpha_pct >= 0 ? "+" : ""}${benchmarkApi.data.alpha_pct.toFixed(1)}%`}
            sub={`Portfolio ${benchmarkApi.data.portfolio_return_pct >= 0 ? "+" : ""}${benchmarkApi.data.portfolio_return_pct.toFixed(1)}% vs ${benchmarkApi.data.benchmark_ticker} ${benchmarkApi.data.benchmark_return_pct >= 0 ? "+" : ""}${benchmarkApi.data.benchmark_return_pct.toFixed(1)}%`}
            trend={benchmarkApi.data.alpha_pct >= 0 ? "up" : "down"}
          />
        )}
      </div>

      {/* Advanced trade metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          label="Profit Factor"
          value={perf?.profit_factor != null ? perf.profit_factor.toFixed(2) : "--"}
          sub="Gross Win / Gross Loss"
        />
        <MetricCard
          label="Expectancy"
          value={perf?.expectancy != null ? `${perf.expectancy.toFixed(2)}%` : "--"}
          sub="Per-trade expected return"
        />
        <MetricCard
          label="Max Win Streak"
          value={String(perf?.max_consecutive_wins ?? 0)}
          sub="consecutive wins"
        />
        <MetricCard
          label="Max Loss Streak"
          value={String(perf?.max_consecutive_losses ?? 0)}
          sub="consecutive losses"
          trend={(perf?.max_consecutive_losses ?? 0) > 3 ? "down" : undefined}
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

      {/* Benchmark comparison */}
      {benchmarkApi.error && (
        <ErrorAlert
          message={benchmarkApi.error}
          onRetry={() => benchmarkApi.refetch()}
        />
      )}
      {benchmarkApi.data && benchmarkApi.data.series.length > 0 && (
        <Card>
          <CardHeader
            title={`Portfolio vs ${benchmarkApi.data.benchmark_ticker}`}
            subtitle="Indexed to 100 at start"
          />
          <CardBody>
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={benchmarkApi.data.series} margin={{ top: 5, right: 10, bottom: 0, left: 10 }}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "#6b7280" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: string) => {
                    const d = new Date(v);
                    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
                  }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#6b7280" }}
                  axisLine={false}
                  tickLine={false}
                  domain={["auto", "auto"]}
                />
                <Tooltip
                  contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#9ca3af" }}
                  formatter={(v: number, name: string) => [
                    v.toFixed(1),
                    name === "portfolio_indexed" ? "Portfolio" : benchmarkApi.data!.benchmark_ticker,
                  ]}
                />
                <ReferenceLine y={100} stroke="#374151" strokeDasharray="3 3" />
                <Line type="monotone" dataKey="portfolio_indexed" stroke="#3b82f6" strokeWidth={2} dot={false} name="portfolio_indexed" />
                <Line type="monotone" dataKey="benchmark_indexed" stroke="#6b7280" strokeWidth={1.5} strokeDasharray="5 5" dot={false} name="benchmark_indexed" />
              </ComposedChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
      )}

      {/* Cumulative Realized P&L chart */}
      <Card>
        <CardHeader title="Cumulative Realized P&L" />
        <CardBody>
          {!cumulativePnlApi.data || cumulativePnlApi.data.length === 0 ? (
            <EmptyState message="No closed trades yet." />
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={cumulativePnlApi.data}>
                <defs>
                  <linearGradient id="colorCumPnlPos" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorCumPnlNeg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
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
                  tickFormatter={(v) => formatCurrency(v)}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#111827",
                    border: "1px solid #374151",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  labelFormatter={(v) => formatDate(String(v))}
                  formatter={(value: number, _name: string) => [
                    formatCurrency(value),
                    "Cumulative P&L",
                  ]}
                />
                <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />
                <Area
                  type="monotone"
                  dataKey="cumulative_pnl"
                  stroke="#10b981"
                  fill="url(#colorCumPnlPos)"
                  strokeWidth={2}
                  name="Cumulative P&L"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardBody>
      </Card>

      {/* Drawdown & Rolling Sharpe */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DrawdownChart />
        <RollingSharpeChart />
      </div>

      {/* Monthly Heatmap */}
      <MonthlyHeatmapCalendar />

      {/* P&L Attribution */}
      <PerformanceAttribution />

      {/* Snapshot Comparison */}
      <SnapshotComparison />

      {/* Monthly returns + Top performers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly returns bar chart */}
        <Card>
          <CardHeader
            title="Monthly Returns"
            action={
              <div className="flex rounded-md overflow-hidden border border-gray-700 text-xs">
                <Button
                  variant={monthlyMode === "dollar" ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => setMonthlyMode("dollar")}
                  className="rounded-none min-h-0 py-1 px-2.5 text-xs"
                >
                  Dollar
                </Button>
                <Button
                  variant={monthlyMode === "percent" ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => setMonthlyMode("percent")}
                  className="rounded-none min-h-0 py-1 px-2.5 text-xs"
                >
                  Percent
                </Button>
              </div>
            }
          />
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
                    tickFormatter={
                      monthlyMode === "dollar"
                        ? (v) => `$${v.toLocaleString()}`
                        : (v) => `${(v as number).toFixed(1)}%`
                    }
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#111827",
                      border: "1px solid #374151",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    formatter={
                      monthlyMode === "dollar"
                        ? (value: number) => [formatCurrency(value), "P&L"]
                        : (value: number) => [`${value.toFixed(2)}%`, "Return"]
                    }
                  />
                  <ReferenceLine y={0} stroke="#4b5563" />
                  <Bar
                    dataKey={monthlyMode === "dollar" ? "pnl" : "return_pct"}
                    radius={[4, 4, 0, 0]}
                    name={monthlyMode === "dollar" ? "P&L" : "Return"}
                  >
                    {monthly.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={
                          monthlyMode === "dollar"
                            ? entry.pnl >= 0 ? "#10b981" : "#ef4444"
                            : entry.return_pct >= 0 ? "#10b981" : "#ef4444"
                        }
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
