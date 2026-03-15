import { useEffect, useMemo, useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useApi } from "../hooks/useApi";
import {
  getPortfolio,
  getAlerts,
  getPositionHistory,
  getValueHistory,
  getWatchlist,
  runMonitorCheck,
  getRegime,
} from "../api/endpoints";
import type {
  Portfolio,
  Alert,
  Position,
  ValueHistoryPoint,
  WatchlistItem,
  RegimeResult,
} from "../api/types";
import MetricCard from "../components/shared/MetricCard";
import RegimeBadge from "../components/shared/RegimeBadge";
import SignalBadge from "../components/shared/SignalBadge";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import WarningsBanner from "../components/shared/WarningsBanner";
import WeeklySummaryCard from "../components/summary/WeeklySummaryCard";
import TopMoversCard from "../components/dashboard/TopMoversCard";
import SignalSummaryCard from "../components/dashboard/SignalSummaryCard";
import DailyReturnCard from "../components/dashboard/DailyReturnCard";
import RiskSummaryWidget from "../components/dashboard/RiskSummaryWidget";
import RegimeTimeline from "../components/dashboard/RegimeTimeline";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { SkeletonCard, SkeletonTable } from "../components/ui/Skeleton";
import { useToast } from "../contexts/ToastContext";
import { formatCurrency, formatRelativeTime } from "../lib/formatters";
import { usePageTitle } from "../hooks/usePageTitle";

const SECTOR_COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#84cc16",
];

interface DriftFlag {
  ticker: string;
  status: "above-target" | "below-stop" | "overdue";
  label: string;
  reason: string;
}

const severityDotMap: Record<string, string> = {
  critical: "bg-red-400",
  high: "bg-red-400",
  medium: "bg-yellow-400",
  low: "bg-emerald-400",
  info: "bg-blue-400",
};

export default function DashboardPage() {
  usePageTitle("Dashboard");
  const navigate = useNavigate();
  const { toast } = useToast();
  const { data, loading, error, warnings, refetch, lastUpdated } = useApi<Portfolio>(
    () => getPortfolio(),
    { cacheKey: "dashboard:portfolio", ttlMs: 30_000 },
  );
  const alertsApi = useApi<Alert[]>(
    () => getAlerts({ limit: 5 }),
    { cacheKey: "dashboard:alerts", ttlMs: 15_000 },
  );
  const historyApi = useApi<Position[]>(
    () => getPositionHistory(),
    { cacheKey: "dashboard:history", ttlMs: 60_000 },
  );
  const valueHistoryApi = useApi<ValueHistoryPoint[]>(
    () => getValueHistory(30),
    { cacheKey: "dashboard:valueHistory", ttlMs: 60_000 },
  );
  const watchlistApi = useApi<WatchlistItem[]>(
    () => getWatchlist(),
    { cacheKey: "dashboard:watchlist", ttlMs: 60_000 },
  );
  const regimeApi = useApi<RegimeResult>(
    () => getRegime(),
    { cacheKey: "dashboard:regime", ttlMs: 60_000 },
  );
  const [healthLoading, setHealthLoading] = useState(false);

  // Auto-refresh all dashboard data every 60 seconds
  const refetchAll = useCallback(() => {
    refetch();
    alertsApi.refetch();
    historyApi.refetch();
    valueHistoryApi.refetch();
    watchlistApi.refetch();
  }, [refetch, alertsApi, historyApi, valueHistoryApi, watchlistApi]);

  useEffect(() => {
    const id = setInterval(refetchAll, 60_000);
    return () => clearInterval(id);
  }, [refetchAll]);

  // Tick to keep "Updated Xm ago" label fresh
  const [, setDisplayTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setDisplayTick((t) => t + 1), 30_000);
    return () => clearInterval(id);
  }, []);

  // Unrealized P&L
  const totalPnl = useMemo(() => {
    if (!data) return { pnl: 0, pnlPct: 0, invested: 0 };
    const positions = data.positions;
    const invested = positions.reduce((s, p) => s + p.cost_basis, 0);
    const pnl = positions.reduce((s, p) => s + p.unrealized_pnl, 0);
    const pnlPct = invested > 0 ? (pnl / invested) * 100 : 0;
    return { pnl, pnlPct, invested };
  }, [data]);

  // Realized P&L from closed positions
  const totalRealizedPnl = useMemo(() => {
    if (!historyApi.data) return 0;
    return historyApi.data.reduce((s, p) => s + (p.realized_pnl ?? 0), 0);
  }, [historyApi.data]);

  // Chart data: format dates for display
  const chartData = useMemo(() => {
    if (!valueHistoryApi.data) return [];
    return valueHistoryApi.data.map((pt) => ({
      ...pt,
      label: new Date(pt.date).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
    }));
  }, [valueHistoryApi.data]);

  async function handleHealthCheck() {
    setHealthLoading(true);
    try {
      await runMonitorCheck();
      toast.success("Health check complete");
    } catch (err) {
      toast.error(
        "Health check failed",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setHealthLoading(false);
    }
  }

  if (loading)
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 xl:grid-cols-5 gap-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <SkeletonTable rows={5} columns={4} />
      </div>
    );
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;
  if (!data) return null;

  const pnlTrend = totalPnl.pnl >= 0 ? ("up" as const) : ("down" as const);
  const pnlSign = totalPnl.pnl >= 0 ? "+" : "";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          {regimeApi.data && !regimeApi.loading && !regimeApi.error && (
            <RegimeBadge regime={regimeApi.data.regime} />
          )}
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-gray-500">
              Updated {formatRelativeTime(lastUpdated)}
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={refetchAll}>
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M23 4v6h-6" />
              <path d="M1 20v-6h6" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            Refresh
          </Button>
        </div>
      </div>
      <WarningsBanner warnings={[...warnings, ...alertsApi.warnings]} />

      {/* ── Top row: 5 metric cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-4 xl:grid-cols-5 gap-4">
        <MetricCard
          label="Portfolio Value"
          value={formatCurrency(data.total_value)}
          sub={`${data.positions.length} positions`}
        />
        <MetricCard
          label="Unrealized P&L"
          value={`${pnlSign}${formatCurrency(totalPnl.pnl)}`}
          sub={`${pnlSign}${totalPnl.pnlPct.toFixed(1)}%`}
          trend={pnlTrend}
        />
        <MetricCard
          label="Realized P&L"
          value={`${totalRealizedPnl >= 0 ? "+" : ""}${formatCurrency(totalRealizedPnl)}`}
          sub={`${historyApi.data?.length ?? 0} closed`}
          trend={totalRealizedPnl >= 0 ? "up" : "down"}
        />
        <MetricCard
          label="Cash"
          value={formatCurrency(data.cash)}
          sub={`${(data.cash_pct * 100).toFixed(1)}% of portfolio`}
        />
        <DailyReturnCard />
      </div>

      {/* ── Top Movers + Signal Summary + Risk Overview ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TopMoversCard positions={data.positions} />
        <SignalSummaryCard />
      </div>

      {/* ── Risk Summary Widget ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RiskSummaryWidget />
      </div>

      {/* ── Portfolio value sparkline ── */}
      <Card padding="sm">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Portfolio Value (30 Days)
        </h3>
        {valueHistoryApi.loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-600 border-t-blue-400" />
          </div>
        ) : valueHistoryApi.error ? (
          <p className="text-xs text-red-400">
            Failed to load chart data.
          </p>
        ) : chartData.length === 0 ? (
          <EmptyState message="No value history yet." />
        ) : (
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart
              data={chartData}
              margin={{ top: 4, right: 4, bottom: 0, left: 4 }}
            >
              <defs>
                <linearGradient id="valGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: "#6b7280" }}
                axisLine={false}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fontSize: 10, fill: "#6b7280" }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  background: "#1f2937",
                  border: "1px solid #374151",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#9ca3af" }}
                formatter={(v: number) => [formatCurrency(v), "Value"]}
              />
              <Area
                type="monotone"
                dataKey="total_value"
                stroke="#3b82f6"
                strokeWidth={2}
                fill="url(#valGrad)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* ── Regime History Timeline ── */}
      <RegimeTimeline />

      {/* ── Sector Allocation + Thesis Drift ── */}
      {(() => {
        // Sector allocation data
        const sectorEntries = Object.entries(data.sector_breakdown);
        const hasDiversification = sectorEntries.length > 1;
        const sectorTotal = sectorEntries.reduce((s, [, v]) => s + v, 0);

        // Thesis drift flags
        const driftFlags: DriftFlag[] = [];
        for (const pos of data.positions) {
          if (
            pos.target_price != null &&
            pos.current_price > pos.target_price * 1.1
          ) {
            driftFlags.push({
              ticker: pos.ticker,
              status: "above-target",
              label: "Above Target",
              reason: `Price ${formatCurrency(pos.current_price)} exceeds target ${formatCurrency(pos.target_price)} by >10%`,
            });
          }
          if (pos.stop_loss != null && pos.current_price < pos.stop_loss) {
            driftFlags.push({
              ticker: pos.ticker,
              status: "below-stop",
              label: "Below Stop",
              reason: `Price ${formatCurrency(pos.current_price)} is below stop loss ${formatCurrency(pos.stop_loss)}`,
            });
          }
          if (
            pos.expected_hold_days != null &&
            pos.holding_days > pos.expected_hold_days
          ) {
            driftFlags.push({
              ticker: pos.ticker,
              status: "overdue",
              label: "Overdue",
              reason: `Held ${pos.holding_days}d vs expected ${pos.expected_hold_days}d`,
            });
          }
        }

        const driftBadgeClass: Record<string, string> = {
          "above-target": "bg-yellow-500/20 text-yellow-400",
          "below-stop": "bg-red-500/20 text-red-400",
          overdue: "bg-orange-500/20 text-orange-400",
        };

        return (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Sector Allocation */}
            <Card padding="md">
              <h2 className="text-sm font-semibold text-gray-300 mb-3">
                Sector Allocation
              </h2>
              {!hasDiversification ? (
                <p className="text-sm text-gray-500">
                  No diversification data
                </p>
              ) : (
                <div>
                  {/* Stacked bar */}
                  <div className="flex h-6 w-full rounded overflow-hidden">
                    {sectorEntries.map(([sector, pct], i) => (
                      <div
                        key={sector}
                        style={{
                          width: `${sectorTotal > 0 ? (pct / sectorTotal) * 100 : 0}%`,
                          backgroundColor:
                            SECTOR_COLORS[i % SECTOR_COLORS.length],
                        }}
                        title={`${sector}: ${(pct * 100).toFixed(1)}%`}
                      />
                    ))}
                  </div>
                  {/* Legend */}
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
                    {sectorEntries.map(([sector, pct], i) => (
                      <div
                        key={sector}
                        className="flex items-center gap-1.5 text-xs text-gray-300"
                      >
                        <span
                          className="inline-block w-2.5 h-2.5 rounded-sm shrink-0"
                          style={{
                            backgroundColor:
                              SECTOR_COLORS[i % SECTOR_COLORS.length],
                          }}
                        />
                        <span>
                          {sector}{" "}
                          <span className="text-gray-500">
                            {(pct * 100).toFixed(1)}%
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>

            {/* Thesis Drift */}
            <Card padding="md">
              <h2 className="text-sm font-semibold text-gray-300 mb-3">
                Thesis Drift
              </h2>
              {driftFlags.length === 0 ? (
                <p className="text-sm text-gray-500">
                  All positions on track.
                </p>
              ) : (
                <div className="space-y-2">
                  {driftFlags.map((flag) => (
                    <div
                      key={`${flag.ticker}-${flag.status}`}
                      className="flex items-center gap-2 text-sm"
                    >
                      <span className="font-mono font-medium text-white w-14 shrink-0">
                        {flag.ticker}
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs font-medium shrink-0 ${driftBadgeClass[flag.status]}`}
                      >
                        {flag.label}
                      </span>
                      <span className="text-gray-400 text-xs truncate">
                        {flag.reason}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        );
      })()}

      {/* ── Middle row: Open positions + Recent alerts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Open positions mini-table (3/5) */}
        <Card padding="md" className="lg:col-span-3">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">
            Open Positions
          </h2>
          {data.positions.length === 0 ? (
            <EmptyState message="No open positions." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800/50">
                    <th className="text-left py-2 pr-4">Ticker</th>
                    <th className="text-right py-2 px-4">Price</th>
                    <th className="text-right py-2 px-4">P&L %</th>
                    <th className="text-right py-2 pl-4">Days</th>
                  </tr>
                </thead>
                <tbody>
                  {data.positions.map((pos) => {
                    const pnlPct = pos.unrealized_pnl_pct * 100;
                    const pnlColor =
                      pnlPct >= 0 ? "text-green-400" : "text-red-400";
                    return (
                      <tr
                        key={pos.ticker}
                        className="border-b border-gray-800/30 last:border-0 hover:bg-gray-800/40 cursor-pointer transition-colors"
                        onClick={() => navigate(`/portfolio/${pos.ticker}`)}
                      >
                        <td className="py-2 pr-4 font-mono font-medium">
                          <Link to={`/portfolio/${pos.ticker}`} className="text-white hover:text-blue-400 transition-colors">
                            {pos.ticker}
                          </Link>
                        </td>
                        <td className="py-2 px-4 text-right text-gray-300">
                          {formatCurrency(pos.current_price)}
                        </td>
                        <td
                          className={`py-2 px-4 text-right font-medium ${pnlColor}`}
                        >
                          {pnlPct >= 0 ? "+" : ""}
                          {pnlPct.toFixed(1)}%
                        </td>
                        <td className="py-2 pl-4 text-right text-gray-400">
                          {pos.holding_days}d
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Recent alerts (2/5) */}
        <Card padding="md" className="lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-300">
              Recent Alerts
            </h2>
            <button
              onClick={() => navigate("/monitoring")}
              className="text-xs text-blue-400 hover:text-blue-300 transition-colors duration-150"
            >
              View all
            </button>
          </div>
          {alertsApi.loading ? (
            <div className="flex items-center justify-center py-6">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-600 border-t-blue-400" />
            </div>
          ) : alertsApi.data && alertsApi.data.length > 0 ? (
            <ul className="space-y-2">
              {alertsApi.data.slice(0, 5).map((alert) => (
                <li
                  key={alert.id}
                  className="flex items-start gap-2 text-sm"
                >
                  <span
                    className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${
                      severityDotMap[alert.severity] ?? "bg-gray-500"
                    }`}
                  />
                  <div className="min-w-0">
                    <span className="text-gray-300">
                      {alert.ticker && (
                        <span className="font-mono text-white mr-1">
                          {alert.ticker}
                        </span>
                      )}
                      {alert.message.length > 60
                        ? alert.message.slice(0, 60) + "\u2026"
                        : alert.message}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No recent alerts." />
          )}
        </Card>
      </div>

      {/* ── Watchlist highlights ── */}
      <Card padding="sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Watchlist
          </h3>
          <Link
            to="/watchlist"
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors duration-150"
          >
            View all &rarr;
          </Link>
        </div>
        {watchlistApi.loading ? (
          <div className="flex items-center justify-center py-6">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-600 border-t-blue-400" />
          </div>
        ) : watchlistApi.error ? (
          <p className="text-xs text-red-400">
            Failed to load watchlist.
          </p>
        ) : !watchlistApi.data || watchlistApi.data.length === 0 ? (
          <EmptyState message="Watchlist is empty." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800/50">
                  <th className="text-left py-2 pr-4">Ticker</th>
                  <th className="text-left py-2 px-4">Signal</th>
                  <th className="text-right py-2 px-4">Confidence</th>
                  <th className="text-right py-2 pl-4">Target</th>
                </tr>
              </thead>
              <tbody>
                {watchlistApi.data.slice(0, 5).map((item) => (
                  <tr
                    key={item.ticker}
                    className="border-b border-gray-800/30 last:border-0"
                  >
                    <td className="py-2 pr-4 font-mono text-white font-medium">
                      {item.ticker}
                    </td>
                    <td className="py-2 px-4">
                      {item.last_signal ? (
                        <SignalBadge signal={item.last_signal} />
                      ) : (
                        <span className="text-xs text-gray-500">--</span>
                      )}
                    </td>
                    <td className="py-2 px-4 text-right text-gray-300">
                      {item.last_confidence != null
                        ? `${(item.last_confidence * 100).toFixed(0)}%`
                        : "--"}
                    </td>
                    <td className="py-2 pl-4 text-right text-gray-400">
                      {item.target_buy_price != null
                        ? formatCurrency(item.target_buy_price)
                        : "--"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ── Bottom row: Quick actions + Weekly summary ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quick actions */}
        <Card padding="md">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">
            Quick Actions
          </h2>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate("/analyze")}
            >
              Analyze Ticker
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={healthLoading}
              onClick={handleHealthCheck}
            >
              Run Health Check
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate("/signals")}
            >
              View Signals
            </Button>
          </div>
        </Card>

        {/* Weekly summary */}
        <WeeklySummaryCard />
      </div>
    </div>
  );
}
