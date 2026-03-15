import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useApi } from "../hooks/useApi";
import {
  getPortfolio,
  getPositionHistory,
  getThesis,
  getPriceHistory,
  getSignalHistory,
  getAlerts,
  getPositionPnlHistory,
} from "../api/endpoints";
import type {
  Portfolio,
  Position,
  ThesisResponse,
  OhlcvPoint,
  SignalHistoryEntry,
  Alert,
  PositionPnlPoint,
} from "../api/types";
import { Card, CardHeader, CardBody } from "../components/ui/Card";
import { SkeletonCard, Skeleton } from "../components/ui/Skeleton";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import MetricCard from "../components/shared/MetricCard";
import CatalystPanel from "../components/analysis/CatalystPanel";
import { formatCurrency, formatDate, pnlColor } from "../lib/formatters";
import { usePageTitle } from "../hooks/usePageTitle";
import Breadcrumb from "../components/shared/Breadcrumb";
import ThesisEditForm from "../components/portfolio/ThesisEditForm";
import { Button } from "../components/ui/Button";
import PnlTimelineChart from "../components/position/PnlTimelineChart";
import PositionTimeline from "../components/position/PositionTimeline";
import DividendTracker from "../components/portfolio/DividendTracker";
import PositionNotes from "../components/position/PositionNotes";

function statusBadge(status: string) {
  const isOpen = status === "open";
  return (
    <span
      className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
        isOpen
          ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
          : "bg-gray-500/15 text-gray-400 border border-gray-500/30"
      }`}
    >
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function driftIndicator(actual: number | null, expected: number | null, higherIsBetter: boolean) {
  if (actual == null || expected == null) return null;
  const onTrack = higherIsBetter ? actual >= expected : actual <= expected;
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${
        onTrack ? "bg-emerald-400" : "bg-red-400"
      }`}
    />
  );
}

// ---------------------------------------------------------------------------
// Chart tooltip
// ---------------------------------------------------------------------------
interface PriceTTProps {
  active?: boolean;
  payload?: Array<{ value: number; payload: { date: string; close: number } }>;
  label?: string;
}

function PriceTooltip({ active, payload, label }: PriceTTProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  if (!point || point.value == null) return null;
  const date = new Date(label ?? "").toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  return (
    <div className="bg-gray-950/95 border border-gray-700/60 rounded px-2.5 py-1.5 text-[11px] shadow-2xl backdrop-blur-sm">
      <div className="text-gray-500">{date}</div>
      <div className="text-white font-semibold font-mono mt-0.5">
        {formatCurrency(point.value)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Severity helpers for alerts
// ---------------------------------------------------------------------------
const severityStyles: Record<string, string> = {
  critical: "bg-red-500/15 text-red-400 border-red-500/30",
  high: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  low: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  info: "bg-gray-500/15 text-gray-400 border-gray-500/30",
};

// ---------------------------------------------------------------------------
// Loading skeleton for the full page
// ---------------------------------------------------------------------------
function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton variant="text" width="30%" height={20} />
      <div className="flex items-center gap-4">
        <Skeleton variant="text" width={100} height={28} />
        <Skeleton variant="rectangular" width={60} height={24} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }, (_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
      <SkeletonCard className="h-[200px]" />
      <SkeletonCard className="h-[300px]" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export default function PositionDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  usePageTitle(ticker ?? "Position");

  // Fetch portfolio (open positions)
  const portfolioApi = useApi<Portfolio>(() => getPortfolio());
  // Fetch closed positions
  const historyApi = useApi<Position[]>(() => getPositionHistory());
  // Fetch thesis
  const thesisApi = useApi<ThesisResponse>(
    () => getThesis(ticker!),
    [ticker],
  );
  // Fetch signals for this ticker
  const signalsApi = useApi<SignalHistoryEntry[]>(
    () => getSignalHistory({ ticker: ticker!, limit: 50 }),
    [ticker],
  );
  // Fetch alerts for this ticker
  const alertsApi = useApi<Alert[]>(
    () => getAlerts({ ticker: ticker!, limit: 50 }),
    [ticker],
  );
  // Fetch P&L history for this ticker (used by P&L timeline chart)
  const pnlHistoryApi = useApi<PositionPnlPoint[]>(
    () => getPositionPnlHistory(ticker!),
    [ticker],
  );

  // Thesis editing state
  const [editing, setEditing] = useState(false);

  // Find the position from either open or closed
  const position = useMemo<Position | null>(() => {
    if (portfolioApi.data) {
      const found = portfolioApi.data.positions.find(
        (p) => p.ticker.toLowerCase() === ticker?.toLowerCase(),
      );
      if (found) return found;
    }
    if (historyApi.data) {
      const found = historyApi.data.find(
        (p) => p.ticker.toLowerCase() === ticker?.toLowerCase(),
      );
      if (found) return found;
    }
    return null;
  }, [portfolioApi.data, historyApi.data, ticker]);

  // Fetch price history once we know asset_type
  const assetType = position?.asset_type ?? "stock";
  const priceApi = useApi<OhlcvPoint[]>(
    () => getPriceHistory(ticker!, assetType, "1y"),
    [ticker, assetType],
  );

  // Loading state
  const loading = portfolioApi.loading || historyApi.loading;
  if (loading) return <DetailSkeleton />;

  // Error state
  const error = portfolioApi.error || historyApi.error;
  if (error) return <ErrorAlert message={error} onRetry={() => { portfolioApi.refetch(); historyApi.refetch(); }} />;

  // Position not found
  if (!position) {
    return (
      <div className="space-y-6">
        <Breadcrumb items={[
          { label: "Home", href: "/" },
          { label: "Portfolio", href: "/portfolio" },
          { label: ticker ?? "Position" },
        ]} />
        <EmptyState
          message={`Position "${ticker}" not found.`}
          hint="It may have been removed or the ticker is incorrect."
        />
      </div>
    );
  }

  const isClosed = position.status === "closed";
  const thesis = thesisApi.data;
  const actualReturnPct = isClosed
    ? position.realized_pnl != null && position.cost_basis > 0
      ? (position.realized_pnl / position.cost_basis) * 100
      : 0
    : position.unrealized_pnl_pct * 100;

  return (
    <div className="space-y-6">
      {/* -- Breadcrumb -- */}
      <Breadcrumb items={[
        { label: "Home", href: "/" },
        { label: "Portfolio", href: "/portfolio" },
        { label: ticker ?? "Position" },
      ]} />

      {/* -- Header -- */}
      <div className="flex flex-wrap items-center gap-4">
        <h1 className="text-2xl font-bold text-white font-mono">
          {position.ticker}
        </h1>
        {statusBadge(position.status)}
        <span className="text-sm text-gray-500">
          {position.asset_type}
        </span>
        <span className="text-sm text-gray-500">
          Entry: {formatDate(position.entry_date)}
        </span>
        <span className="text-sm text-gray-500">
          {position.holding_days}d held
        </span>
      </div>

      {/* -- P&L Summary -- */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          label="Cost Basis"
          value={formatCurrency(position.cost_basis)}
          sub={`${position.quantity} @ ${formatCurrency(position.avg_cost)}`}
        />
        {isClosed ? (
          <>
            <MetricCard
              label="Exit Price"
              value={
                position.exit_price != null
                  ? formatCurrency(position.exit_price)
                  : "--"
              }
              sub={
                position.exit_reason
                  ? position.exit_reason.replace("_", " ")
                  : undefined
              }
            />
            <MetricCard
              label="Realized P&L"
              value={`${(position.realized_pnl ?? 0) >= 0 ? "+" : ""}${formatCurrency(position.realized_pnl ?? 0)}`}
              sub={`${actualReturnPct >= 0 ? "+" : ""}${actualReturnPct.toFixed(1)}%`}
              trend={(position.realized_pnl ?? 0) >= 0 ? "up" : "down"}
            />
            <MetricCard
              label="Exit Date"
              value={
                position.exit_date ? formatDate(position.exit_date) : "--"
              }
              sub={`${position.holding_days}d held`}
            />
          </>
        ) : (
          <>
            <MetricCard
              label="Current Value"
              value={formatCurrency(position.market_value)}
              sub={`Price: ${formatCurrency(position.current_price)}`}
            />
            <MetricCard
              label="Unrealized P&L"
              value={`${position.unrealized_pnl >= 0 ? "+" : ""}${formatCurrency(position.unrealized_pnl)}`}
              sub={`${position.unrealized_pnl_pct >= 0 ? "+" : ""}${(position.unrealized_pnl_pct * 100).toFixed(1)}%`}
              trend={position.unrealized_pnl >= 0 ? "up" : "down"}
            />
            <MetricCard
              label="Holding Period"
              value={`${position.holding_days}d`}
              sub={
                position.expected_hold_days != null
                  ? `Expected: ${position.expected_hold_days}d`
                  : undefined
              }
            />
          </>
        )}
      </div>

      {/* -- P&L Performance Bar (open positions with stop/target) -- */}
      {!isClosed &&
        (position.stop_loss != null || position.target_price != null) && (
          <PnlPerformanceBar
            currentPrice={position.current_price}
            entryPrice={position.avg_cost}
            stopLoss={position.stop_loss}
            targetPrice={position.target_price}
          />
        )}

      {/* -- Thesis vs Reality -- */}
      <Card>
        <CardHeader
          title="Thesis vs Reality"
          action={
            !editing && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditing(true)}
              >
                Edit Thesis
              </Button>
            )
          }
        />
        <CardBody>
          {editing ? (
            <ThesisEditForm
              ticker={ticker!}
              initialValues={{
                thesis_text: thesis?.thesis_text ?? null,
                target_price: thesis?.target_price ?? null,
                stop_loss: thesis?.stop_loss ?? null,
                expected_hold_days: thesis?.expected_hold_days ?? null,
                expected_return_pct: thesis?.expected_return_pct ?? null,
              }}
              onSaved={() => {
                setEditing(false);
                thesisApi.refetch();
              }}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <>
              {!thesis && thesisApi.loading && (
                <div className="space-y-3">
                  <Skeleton variant="text" lines={3} />
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-3">
                    {Array.from({ length: 4 }, (_, i) => (
                      <SkeletonCard key={i} />
                    ))}
                  </div>
                </div>
              )}

              {thesisApi.error && (
                <p className="text-gray-500 text-sm">
                  Could not load thesis data.
                </p>
              )}

              {thesis && (
                <div className="space-y-4">
                  {/* Thesis text */}
                  {thesis.thesis_text && (
                    <div>
                      <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500 mb-1">
                        Thesis
                      </div>
                      <p className="text-sm text-gray-300 leading-relaxed">
                        {thesis.thesis_text}
                      </p>
                    </div>
                  )}

                  {/* Comparison grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-3">
                    {/* Expected vs Actual return */}
                    <div className="rounded-lg bg-gray-800/40 border border-gray-700/30 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] uppercase tracking-wider text-gray-500">
                          Return
                        </span>
                        {driftIndicator(
                          actualReturnPct,
                          thesis.expected_return_pct != null
                            ? thesis.expected_return_pct * 100
                            : null,
                          true,
                        )}
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500">Expected</span>
                          <span className="text-gray-300 font-mono">
                            {thesis.expected_return_pct != null
                              ? `${(thesis.expected_return_pct * 100).toFixed(1)}%`
                              : "--"}
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500">Actual</span>
                          <span className={`font-mono font-medium ${pnlColor(actualReturnPct)}`}>
                            {actualReturnPct >= 0 ? "+" : ""}
                            {actualReturnPct.toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Hold days */}
                    <div className="rounded-lg bg-gray-800/40 border border-gray-700/30 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] uppercase tracking-wider text-gray-500">
                          Hold Days
                        </span>
                        {driftIndicator(
                          thesis.expected_hold_days != null
                            ? thesis.expected_hold_days - thesis.hold_days_elapsed
                            : null,
                          thesis.expected_hold_days != null ? 0 : null,
                          true,
                        )}
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500">Expected</span>
                          <span className="text-gray-300 font-mono">
                            {thesis.expected_hold_days != null
                              ? `${thesis.expected_hold_days}d`
                              : "--"}
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500">Elapsed</span>
                          <span
                            className={`font-mono font-medium ${
                              thesis.expected_hold_days != null &&
                              thesis.hold_days_elapsed > thesis.expected_hold_days
                                ? "text-red-400"
                                : "text-gray-300"
                            }`}
                          >
                            {thesis.hold_days_elapsed}d
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Target price */}
                    <div className="rounded-lg bg-gray-800/40 border border-gray-700/30 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] uppercase tracking-wider text-gray-500">
                          Target Price
                        </span>
                        {!isClosed &&
                          driftIndicator(
                            position.current_price,
                            thesis.target_price,
                            true,
                          )}
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500">Target</span>
                          <span className="text-gray-300 font-mono">
                            {thesis.target_price != null
                              ? formatCurrency(thesis.target_price)
                              : "--"}
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500">
                            {isClosed ? "Exit" : "Current"}
                          </span>
                          <span className="text-gray-300 font-mono">
                            {isClosed
                              ? position.exit_price != null
                                ? formatCurrency(position.exit_price)
                                : "--"
                              : formatCurrency(position.current_price)}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Stop loss */}
                    <div className="rounded-lg bg-gray-800/40 border border-gray-700/30 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] uppercase tracking-wider text-gray-500">
                          Stop Loss
                        </span>
                        {!isClosed &&
                          thesis.stop_loss != null &&
                          driftIndicator(
                            position.current_price,
                            thesis.stop_loss,
                            true,
                          )}
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500">Stop</span>
                          <span className="text-gray-300 font-mono">
                            {thesis.stop_loss != null
                              ? formatCurrency(thesis.stop_loss)
                              : "--"}
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500">
                            {isClosed ? "Exit" : "Current"}
                          </span>
                          <span className="text-gray-300 font-mono">
                            {isClosed
                              ? position.exit_price != null
                                ? formatCurrency(position.exit_price)
                                : "--"
                              : formatCurrency(position.current_price)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Drift summary */}
                  {(thesis.return_drift_pct != null || thesis.hold_drift_days != null) && (
                    <div className="flex flex-wrap gap-4 mt-2 pt-3 border-t border-gray-800/50">
                      {thesis.return_drift_pct != null && (
                        <div className="text-xs">
                          <span className="text-gray-500">Return drift: </span>
                          <span
                            className={`font-mono font-medium ${
                              Math.abs(thesis.return_drift_pct * 100) > 10
                                ? "text-red-400"
                                : "text-gray-300"
                            }`}
                          >
                            {thesis.return_drift_pct >= 0 ? "+" : ""}
                            {(thesis.return_drift_pct * 100).toFixed(1)}%
                          </span>
                        </div>
                      )}
                      {thesis.hold_drift_days != null && (
                        <div className="text-xs">
                          <span className="text-gray-500">Hold drift: </span>
                          <span
                            className={`font-mono font-medium ${
                              thesis.hold_drift_days > 0 ? "text-red-400" : "text-gray-300"
                            }`}
                          >
                            {thesis.hold_drift_days > 0 ? "+" : ""}
                            {thesis.hold_drift_days}d
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {!thesis.thesis_text &&
                    thesis.expected_return_pct == null &&
                    thesis.expected_hold_days == null &&
                    thesis.target_price == null &&
                    thesis.stop_loss == null && (
                      <p className="text-gray-500 text-sm">
                        No thesis recorded for this position.
                      </p>
                    )}
                </div>
              )}

              {!thesis && !thesisApi.loading && !thesisApi.error && (
                <p className="text-gray-500 text-sm">
                  No thesis recorded for this position.
                </p>
              )}
            </>
          )}
        </CardBody>
      </Card>

      {/* -- Trade Summary (closed positions only) -- */}
      {isClosed && (
        <Card>
          <CardHeader title="Trade Summary" />
          <CardBody>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
              <div className="rounded-lg bg-gray-800/40 border border-gray-700/30 p-3">
                <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
                  Entry &rarr; Exit
                </div>
                <div className="text-sm text-gray-200 font-mono">
                  {formatCurrency(position.avg_cost)} &rarr;{" "}
                  {position.exit_price != null
                    ? formatCurrency(position.exit_price)
                    : "--"}
                </div>
              </div>
              <div className="rounded-lg bg-gray-800/40 border border-gray-700/30 p-3">
                <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
                  Return
                </div>
                <div className={`text-sm font-mono font-medium ${pnlColor(actualReturnPct)}`}>
                  {actualReturnPct >= 0 ? "+" : ""}
                  {actualReturnPct.toFixed(1)}%
                </div>
              </div>
              <div className="rounded-lg bg-gray-800/40 border border-gray-700/30 p-3">
                <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
                  P&amp;L
                </div>
                <div className={`text-sm font-mono font-medium ${pnlColor(position.realized_pnl ?? 0)}`}>
                  {(position.realized_pnl ?? 0) >= 0 ? "+" : ""}
                  {formatCurrency(position.realized_pnl ?? 0)}
                </div>
              </div>
              <div className="rounded-lg bg-gray-800/40 border border-gray-700/30 p-3">
                <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
                  Duration
                </div>
                <div className="text-sm text-gray-200 font-mono">
                  {position.holding_days}d
                </div>
              </div>
              <div className="rounded-lg bg-gray-800/40 border border-gray-700/30 p-3">
                <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
                  Sector
                </div>
                <div className="text-sm text-gray-200">
                  {position.sector ?? "N/A"}
                </div>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* -- Price Chart -- */}
      <Card>
        <CardHeader title="Price History" />
        <CardBody>
          {priceApi.loading && (
            <div className="space-y-3">
              <Skeleton variant="rectangular" height={256} />
              <Skeleton variant="text" width="60%" />
            </div>
          )}

          {priceApi.error && (
            <p className="text-gray-500 text-sm">
              Could not load price data.
            </p>
          )}

          {priceApi.data && priceApi.data.length > 0 && (
            <PriceChart
              data={priceApi.data}
              entryPrice={position.avg_cost}
              targetPrice={position.target_price}
              stopLoss={position.stop_loss}
            />
          )}

          {priceApi.data && priceApi.data.length === 0 && !priceApi.loading && (
            <EmptyState message="No price history available." />
          )}
        </CardBody>
      </Card>

      {/* -- P&L Timeline -- */}
      {!isClosed && pnlHistoryApi.data && pnlHistoryApi.data.length > 0 && (
        <PnlTimelineChart data={pnlHistoryApi.data} />
      )}

      {/* -- Linked Signals + Alert History -- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Signals */}
        <Card>
          <CardHeader title="Linked Signals" />
          <CardBody>
            {signalsApi.loading && (
              <Skeleton variant="text" lines={5} />
            )}

            {signalsApi.error && (
              <p className="text-gray-500 text-sm">
                Could not load signals.
              </p>
            )}

            {signalsApi.data && signalsApi.data.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm table-auto">
                  <thead>
                    <tr className="border-b border-gray-800/50">
                      <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                        Date
                      </th>
                      <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                        Signal
                      </th>
                      <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                        Confidence
                      </th>
                      <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                        Score
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {signalsApi.data.map((sig) => (
                      <tr
                        key={sig.id}
                        className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors"
                      >
                        <td className="px-3 py-2 whitespace-nowrap text-gray-500 text-xs">
                          {formatDate(sig.created_at)}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              sig.final_signal === "BUY"
                                ? "bg-emerald-500/15 text-emerald-400"
                                : sig.final_signal === "SELL"
                                  ? "bg-red-500/15 text-red-400"
                                  : "bg-gray-500/15 text-gray-400"
                            }`}
                          >
                            {sig.final_signal}
                          </span>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-gray-300 font-mono text-xs">
                          {(sig.final_confidence * 100).toFixed(0)}%
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-gray-400 font-mono text-xs">
                          {sig.consensus_score.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              signalsApi.data &&
              !signalsApi.loading && (
                <EmptyState message="No signals found for this ticker." />
              )
            )}
          </CardBody>
        </Card>

        {/* Alerts */}
        <Card>
          <CardHeader title="Alert History" />
          <CardBody>
            {alertsApi.loading && (
              <Skeleton variant="text" lines={5} />
            )}

            {alertsApi.error && (
              <p className="text-gray-500 text-sm">
                Could not load alerts.
              </p>
            )}

            {alertsApi.data && alertsApi.data.length > 0 ? (
              <div className="space-y-2">
                {alertsApi.data.map((alert) => (
                  <div
                    key={alert.id}
                    className="rounded-lg bg-gray-800/30 border border-gray-700/30 p-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                              severityStyles[alert.severity] ??
                              severityStyles.info
                            }`}
                          >
                            {alert.severity.toUpperCase()}
                          </span>
                          <span className="text-[10px] text-gray-600">
                            {alert.alert_type}
                          </span>
                        </div>
                        <p className="text-xs text-gray-300 leading-relaxed">
                          {alert.message}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span className="text-[10px] text-gray-600">
                          {formatDate(alert.created_at)}
                        </span>
                        <span
                          className={`text-[10px] ${
                            alert.acknowledged
                              ? "text-emerald-500"
                              : "text-yellow-500"
                          }`}
                        >
                          {alert.acknowledged ? "Acked" : "Pending"}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              alertsApi.data &&
              !alertsApi.loading && (
                <EmptyState message="No alerts found for this ticker." />
              )
            )}
          </CardBody>
        </Card>
      </div>

      {/* -- News & Catalysts -- */}
      <CatalystPanel ticker={ticker!} assetType={assetType} />

      {/* -- Quick Notes -- */}
      <PositionNotes ticker={ticker!} />

      {/* -- Dividends -- */}
      <DividendTracker ticker={ticker!} />

      {/* -- Position Timeline -- */}
      <PositionTimeline ticker={ticker!} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Price chart sub-component
// ---------------------------------------------------------------------------
function PriceChart({
  data,
  entryPrice,
  targetPrice,
  stopLoss,
}: {
  data: OhlcvPoint[];
  entryPrice: number;
  targetPrice: number | null;
  stopLoss: number | null;
}) {
  const chartData = useMemo(() => {
    return data.map((d) => ({
      date: d.date,
      close: d.close,
    }));
  }, [data]);

  // Compute domain
  const domain = useMemo(() => {
    const prices = chartData.map((d) => d.close);
    const allPrices = [...prices, entryPrice];
    if (targetPrice != null) allPrices.push(targetPrice);
    if (stopLoss != null) allPrices.push(stopLoss);
    const min = Math.min(...allPrices);
    const max = Math.max(...allPrices);
    const pad = (max - min) * 0.08 || max * 0.05;
    return [Math.max(0, min - pad), max + pad] as [number, number];
  }, [chartData, entryPrice, targetPrice, stopLoss]);

  const lastPrice = chartData.length > 0 ? chartData[chartData.length - 1]!.close : 0;
  const firstPrice = chartData.length > 0 ? chartData[0]!.close : 0;
  const isUp = lastPrice >= firstPrice;
  const lineColor = isUp ? "#22c55e" : "#ef4444";

  return (
    <div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ top: 4, right: 0, left: 0, bottom: 0 }}
          >
            <XAxis
              dataKey="date"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#4b5563", fontSize: 10 }}
              tickFormatter={(v: string) =>
                new Date(v).toLocaleDateString("en-US", {
                  month: "short",
                  year: "2-digit",
                })
              }
              minTickGap={40}
            />
            <YAxis
              domain={domain}
              orientation="right"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#4b5563", fontSize: 10 }}
              tickFormatter={(v: number) =>
                v >= 1000
                  ? `$${(v / 1000).toFixed(0)}k`
                  : `$${v.toFixed(0)}`
              }
              width={52}
            />
            <Tooltip
              content={<PriceTooltip />}
              cursor={{
                stroke: "#6b7280",
                strokeWidth: 1,
                strokeDasharray: "2 2",
              }}
            />

            {/* Entry price reference */}
            <ReferenceLine
              y={entryPrice}
              stroke="#60a5fa"
              strokeDasharray="6 4"
              label={{
                value: `Entry $${entryPrice.toFixed(0)}`,
                position: "left",
                fill: "#60a5fa",
                fontSize: 10,
              }}
            />

            {/* Target price reference */}
            {targetPrice != null && (
              <ReferenceLine
                y={targetPrice}
                stroke="#22c55e"
                strokeDasharray="4 4"
                label={{
                  value: `Target $${targetPrice.toFixed(0)}`,
                  position: "left",
                  fill: "#22c55e",
                  fontSize: 10,
                }}
              />
            )}

            {/* Stop loss reference */}
            {stopLoss != null && (
              <ReferenceLine
                y={stopLoss}
                stroke="#ef4444"
                strokeDasharray="4 4"
                label={{
                  value: `Stop $${stopLoss.toFixed(0)}`,
                  position: "left",
                  fill: "#ef4444",
                  fontSize: 10,
                }}
              />
            )}

            <Line
              type="monotone"
              dataKey="close"
              stroke={lineColor}
              dot={false}
              strokeWidth={1.5}
              activeDot={{
                r: 3,
                fill: lineColor,
                stroke: "#111827",
                strokeWidth: 2,
              }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="mt-2 flex flex-wrap items-center gap-4 px-1">
        <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
          <span
            className="inline-block w-3 h-0.5 rounded"
            style={{ backgroundColor: lineColor }}
          />
          Close Price
        </span>
        <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
          <span className="inline-block w-3 h-0.5 border-t border-dashed border-blue-400" />
          Entry
        </span>
        {targetPrice != null && (
          <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
            <span className="inline-block w-3 h-0.5 border-t border-dashed border-emerald-400" />
            Target
          </span>
        )}
        {stopLoss != null && (
          <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
            <span className="inline-block w-3 h-0.5 border-t border-dashed border-red-400" />
            Stop Loss
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// P&L Performance Bar sub-component (open positions only)
// ---------------------------------------------------------------------------
function PnlPerformanceBar({
  currentPrice,
  entryPrice,
  stopLoss,
  targetPrice,
}: {
  currentPrice: number;
  entryPrice: number;
  stopLoss: number | null;
  targetPrice: number | null;
}) {
  // Determine the range for the bar
  const low = stopLoss ?? entryPrice * 0.85;
  const high = targetPrice ?? entryPrice * 1.15;
  const rangeMin = Math.min(low, entryPrice, currentPrice) * 0.98;
  const rangeMax = Math.max(high, entryPrice, currentPrice) * 1.02;
  const range = rangeMax - rangeMin || 1;

  const pct = (v: number) => ((v - rangeMin) / range) * 100;

  const entryPct = pct(entryPrice);
  const currentPct = Math.max(0, Math.min(100, pct(currentPrice)));
  const stopPct = stopLoss != null ? pct(stopLoss) : null;
  const targetPct = targetPrice != null ? pct(targetPrice) : null;

  // Bar fill: from entry to current
  const fillLeft = Math.min(entryPct, currentPct);
  const fillWidth = Math.abs(currentPct - entryPct);
  const isAboveEntry = currentPrice >= entryPrice;

  return (
    <Card>
      <CardHeader title="Price Range" />
      <CardBody>
        <div className="relative h-3 rounded-full bg-gray-700/50 overflow-hidden">
          {/* Stop zone (left side tint) */}
          {stopPct != null && (
            <div
              className="absolute inset-y-0 left-0 bg-red-500/15 rounded-l-full"
              style={{ width: `${stopPct}%` }}
            />
          )}
          {/* Target zone (right side tint) */}
          {targetPct != null && (
            <div
              className="absolute inset-y-0 right-0 bg-emerald-500/15 rounded-r-full"
              style={{ width: `${100 - targetPct}%` }}
            />
          )}
          {/* Fill bar from entry to current */}
          <div
            className={`absolute inset-y-0 rounded-full ${
              isAboveEntry ? "bg-emerald-500/50" : "bg-red-500/50"
            }`}
            style={{ left: `${fillLeft}%`, width: `${fillWidth}%` }}
          />
          {/* Entry marker (blue line) */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-blue-400"
            style={{ left: `${entryPct}%` }}
          />
          {/* Current price dot */}
          <div
            className={`absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 border-gray-900 ${
              isAboveEntry ? "bg-emerald-400" : "bg-red-400"
            }`}
            style={{ left: `${currentPct}%`, marginLeft: "-6px" }}
          />
        </div>
        {/* Labels */}
        <div className="relative mt-2 h-4">
          {stopLoss != null && (
            <span
              className="absolute text-[10px] text-red-400 font-mono"
              style={{ left: `${stopPct!}%`, transform: "translateX(-50%)" }}
            >
              Stop {formatCurrency(stopLoss)}
            </span>
          )}
          <span
            className="absolute text-[10px] text-blue-400 font-mono"
            style={{ left: `${entryPct}%`, transform: "translateX(-50%)" }}
          >
            Entry {formatCurrency(entryPrice)}
          </span>
          {targetPrice != null && (
            <span
              className="absolute text-[10px] text-emerald-400 font-mono"
              style={{ left: `${targetPct!}%`, transform: "translateX(-50%)" }}
            >
              Target {formatCurrency(targetPrice)}
            </span>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
