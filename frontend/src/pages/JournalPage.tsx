import { Fragment, useMemo, useState } from "react";
import { useApi } from "../hooks/useApi";
import { getPositionHistory, getPerformanceSummary } from "../api/endpoints";
import type { Position, PerformanceSummary } from "../api/types";
import { Card, CardHeader, CardBody } from "../components/ui/Card";
import { SkeletonTable, SkeletonCard } from "../components/ui/Skeleton";
import MetricCard from "../components/shared/MetricCard";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import WarningsBanner from "../components/shared/WarningsBanner";
import { formatCurrency, formatDate } from "../lib/formatters";
import { usePageTitle } from "../hooks/usePageTitle";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function pnlColor(v: number): string {
  if (v > 0) return "text-emerald-400";
  if (v < 0) return "text-red-400";
  return "text-gray-400";
}

function returnPct(pos: Position): number {
  if (
    pos.realized_pnl != null &&
    pos.cost_basis > 0
  ) {
    return (pos.realized_pnl / pos.cost_basis) * 100;
  }
  return 0;
}

// ---------------------------------------------------------------------------
// Expandable row detail
// ---------------------------------------------------------------------------
function TradeDetail({ pos }: { pos: Position }) {
  const actual = returnPct(pos);
  const expectedPct =
    pos.expected_return_pct != null ? pos.expected_return_pct * 100 : null;

  return (
    <tr>
      <td colSpan={10} className="px-4 py-3 bg-gray-800/20 border-b border-gray-800/30">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          {/* Thesis */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Thesis
            </div>
            <p className="text-gray-300 leading-relaxed">
              {pos.thesis_text || "No thesis recorded."}
            </p>
          </div>

          {/* Expected vs Actual Return */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Return: Expected vs Actual
            </div>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-gray-500">Expected</span>
                <span className="text-gray-300 font-mono">
                  {expectedPct != null ? `${expectedPct.toFixed(1)}%` : "--"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Actual</span>
                <span className={`font-mono font-medium ${pnlColor(actual)}`}>
                  {actual >= 0 ? "+" : ""}
                  {actual.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* Hold Days & Targets */}
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
              Hold Days: Expected vs Actual
            </div>
            <div className="space-y-1">
              <div className="flex justify-between">
                <span className="text-gray-500">Expected</span>
                <span className="text-gray-300 font-mono">
                  {pos.expected_hold_days != null
                    ? `${pos.expected_hold_days}d`
                    : "--"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Actual</span>
                <span className="text-gray-300 font-mono">
                  {pos.holding_days}d
                </span>
              </div>
              {pos.target_price != null && (
                <div className="flex justify-between mt-1">
                  <span className="text-gray-500">Target</span>
                  <span className="text-gray-300 font-mono">
                    {formatCurrency(pos.target_price)}
                  </span>
                </div>
              )}
              {pos.stop_loss != null && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Stop Loss</span>
                  <span className="text-gray-300 font-mono">
                    {formatCurrency(pos.stop_loss)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function JournalPage() {
  usePageTitle("Trade Journal");

  const historyApi = useApi<Position[]>(() => getPositionHistory(), {
    cacheKey: "journal:history",
    ttlMs: 60_000,
  });

  const summaryApi = useApi<PerformanceSummary>(
    () => getPerformanceSummary(),
    { cacheKey: "journal:summary", ttlMs: 60_000 },
  );

  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  // Sort closed positions by exit_date DESC
  const closedPositions = useMemo(() => {
    if (!historyApi.data) return [];
    return [...historyApi.data].sort((a, b) => {
      const da = a.exit_date ?? "";
      const db = b.exit_date ?? "";
      return db.localeCompare(da);
    });
  }, [historyApi.data]);

  const loading = historyApi.loading || summaryApi.loading;
  const error = historyApi.error || summaryApi.error;
  const warnings = [...historyApi.warnings, ...summaryApi.warnings];
  const perf = summaryApi.data;

  if (error) return <ErrorAlert message={error} />;

  const pnlTrend =
    perf && perf.total_realized_pnl >= 0 ? "up" : "down";
  const pnlSign = perf && perf.total_realized_pnl >= 0 ? "+" : "";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Trade Journal</h1>
      <WarningsBanner warnings={warnings} />

      {/* Loading skeleton */}
      {loading && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }, (_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
          <SkeletonTable rows={8} columns={8} />
        </>
      )}

      {/* Summary stats */}
      {!loading && perf && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <MetricCard
              label="Total Trades"
              value={String(perf.total_trades)}
              sub={`${perf.win_count}W / ${perf.loss_count}L`}
            />
            <MetricCard
              label="Win Rate"
              value={`${perf.win_rate.toFixed(1)}%`}
              sub={`Avg win +${perf.avg_win_pct.toFixed(1)}% / loss ${perf.avg_loss_pct.toFixed(1)}%`}
              trend={perf.win_rate >= 50 ? "up" : perf.win_rate > 0 ? "down" : undefined}
            />
            <MetricCard
              label="Avg Hold Days"
              value={`${perf.avg_hold_days.toFixed(0)}d`}
            />
            <MetricCard
              label="Total Realized P&L"
              value={`${pnlSign}${formatCurrency(perf.total_realized_pnl)}`}
              trend={pnlTrend}
            />
          </div>

          {/* Best / Worst Trade */}
          {(perf.best_trade || perf.worst_trade) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {perf.best_trade && (
                <Card>
                  <CardHeader title="Best Trade" />
                  <CardBody>
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-mono font-bold text-white">
                        {perf.best_trade.ticker}
                      </span>
                      <div className="text-right">
                        <div className="text-emerald-400 font-mono font-semibold">
                          +{perf.best_trade.return_pct.toFixed(1)}%
                        </div>
                        <div className="text-emerald-400/70 text-sm">
                          +{formatCurrency(perf.best_trade.pnl)}
                        </div>
                      </div>
                    </div>
                  </CardBody>
                </Card>
              )}
              {perf.worst_trade && (
                <Card>
                  <CardHeader title="Worst Trade" />
                  <CardBody>
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-mono font-bold text-white">
                        {perf.worst_trade.ticker}
                      </span>
                      <div className="text-right">
                        <div className="text-red-400 font-mono font-semibold">
                          {perf.worst_trade.return_pct.toFixed(1)}%
                        </div>
                        <div className="text-red-400/70 text-sm">
                          {formatCurrency(perf.worst_trade.pnl)}
                        </div>
                      </div>
                    </div>
                  </CardBody>
                </Card>
              )}
            </div>
          )}
        </>
      )}

      {/* Closed Positions Table */}
      {!loading && (
        <Card>
          <CardHeader
            title="Closed Positions"
            subtitle={`${closedPositions.length} trades`}
          />
          <CardBody className="p-0">
            {closedPositions.length === 0 ? (
              <div className="p-5">
                <EmptyState message="No closed trades yet." />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800/50">
                      <th className="text-left py-2.5 px-4">Ticker</th>
                      <th className="text-left py-2.5 px-4">Entry</th>
                      <th className="text-left py-2.5 px-4">Exit</th>
                      <th className="text-right py-2.5 px-4">Entry $</th>
                      <th className="text-right py-2.5 px-4">Exit $</th>
                      <th className="text-right py-2.5 px-4">Return</th>
                      <th className="text-right py-2.5 px-4">P&L</th>
                      <th className="text-left py-2.5 px-4">Reason</th>
                      <th className="text-right py-2.5 px-4">Days</th>
                      <th className="text-left py-2.5 px-4">Thesis</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closedPositions.map((pos) => {
                      const ret = returnPct(pos);
                      const pnl = pos.realized_pnl ?? 0;
                      const isExpanded = expandedTicker === pos.ticker;

                      return (
                        <Fragment key={`${pos.ticker}-${pos.exit_date}`}>
                          <tr
                            className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors cursor-pointer"
                            onClick={() =>
                              setExpandedTicker(
                                isExpanded ? null : pos.ticker,
                              )
                            }
                          >
                            <td className="py-2.5 px-4 font-mono text-white font-medium">
                              {pos.ticker}
                            </td>
                            <td className="py-2.5 px-4 text-gray-400 whitespace-nowrap">
                              {formatDate(pos.entry_date)}
                            </td>
                            <td className="py-2.5 px-4 text-gray-400 whitespace-nowrap">
                              {pos.exit_date
                                ? formatDate(pos.exit_date)
                                : "--"}
                            </td>
                            <td className="py-2.5 px-4 text-right text-gray-300 font-mono">
                              {formatCurrency(pos.avg_cost)}
                            </td>
                            <td className="py-2.5 px-4 text-right text-gray-300 font-mono">
                              {pos.exit_price != null
                                ? formatCurrency(pos.exit_price)
                                : "--"}
                            </td>
                            <td
                              className={`py-2.5 px-4 text-right font-mono font-medium ${pnlColor(ret)}`}
                            >
                              {ret >= 0 ? "+" : ""}
                              {ret.toFixed(1)}%
                            </td>
                            <td
                              className={`py-2.5 px-4 text-right font-mono ${pnlColor(pnl)}`}
                            >
                              {pnl >= 0 ? "+" : ""}
                              {formatCurrency(pnl)}
                            </td>
                            <td className="py-2.5 px-4 text-gray-400 text-xs">
                              {pos.exit_reason
                                ? pos.exit_reason.replace(/_/g, " ")
                                : "--"}
                            </td>
                            <td className="py-2.5 px-4 text-right text-gray-400 font-mono">
                              {pos.holding_days}
                            </td>
                            <td className="py-2.5 px-4 text-gray-500 text-xs max-w-[200px] truncate">
                              {pos.thesis_text || "--"}
                            </td>
                          </tr>
                          {isExpanded && <TradeDetail pos={pos} />}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
