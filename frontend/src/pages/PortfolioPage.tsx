import { useState, useMemo, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { getPortfolio, addPosition, removePosition, closePosition, getPositionHistory, getAlerts } from "../api/endpoints";
import type { Portfolio, Alert, Position } from "../api/types";
import MetricCard from "../components/shared/MetricCard";
import PositionsTable from "../components/portfolio/PositionsTable";
import AddPositionForm from "../components/portfolio/AddPositionForm";
import type { AddPositionInitialValues } from "../components/portfolio/AddPositionForm";
import AllocationChart from "../components/portfolio/AllocationChart";
import ClosePositionModal from "../components/portfolio/ClosePositionModal";
import ClosedPositionsTable from "../components/portfolio/ClosedPositionsTable";
import DashboardAlertsList from "../components/monitoring/DashboardAlertsList";
import WeeklySummaryCard from "../components/summary/WeeklySummaryCard";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import WarningsBanner from "../components/shared/WarningsBanner";
import { formatCurrency } from "../lib/formatters";
import { usePageTitle } from "../hooks/usePageTitle";
import { invalidateCache } from "../lib/cache";

type BreakdownMode = "ticker" | "sector";

function buildAllocations(p: Portfolio, mode: BreakdownMode): Record<string, number> {
  const alloc: Record<string, number> = {};
  if (mode === "ticker") {
    for (const [ticker, pct] of p.top_concentration) {
      alloc[ticker as string] = pct as number;
    }
  } else {
    Object.assign(alloc, p.sector_breakdown);
  }
  if (p.cash_pct > 0.001) {
    alloc["Cash"] = p.cash_pct;
  }
  return alloc;
}

// ---------------------------------------------------------------------------
// Thesis drift alert computation (from Dashboard)
// ---------------------------------------------------------------------------
interface ThesisDriftAlert {
  ticker: string;
  message: string;
  severity: "green" | "amber" | "red";
}

function computeThesisDriftAlerts(positions: Position[]): ThesisDriftAlert[] {
  const alerts: ThesisDriftAlert[] = [];

  for (const pos of positions) {
    const hasThesis =
      pos.expected_hold_days != null ||
      pos.expected_return_pct != null ||
      pos.stop_loss != null;
    if (!hasThesis) continue;

    // Hold time checks
    if (pos.expected_hold_days != null && pos.expected_hold_days > 0) {
      const ratio = pos.holding_days / pos.expected_hold_days;
      if (ratio > 1.0) {
        const overdue = pos.holding_days - pos.expected_hold_days;
        alerts.push({
          ticker: pos.ticker,
          message: `${pos.ticker}: ${pos.holding_days}/${pos.expected_hold_days}d (${overdue}d overdue)`,
          severity: "red",
        });
      } else if (ratio >= 0.8) {
        alerts.push({
          ticker: pos.ticker,
          message: `${pos.ticker}: ${pos.holding_days}/${pos.expected_hold_days}d (approaching deadline)`,
          severity: "amber",
        });
      }
    }

    // Return exceeding target
    if (pos.expected_return_pct != null && pos.expected_return_pct > 0) {
      const actualRetPct = pos.unrealized_pnl_pct * 100;
      const expectedRetPct = pos.expected_return_pct * 100;
      if (actualRetPct > expectedRetPct * 1.5) {
        alerts.push({
          ticker: pos.ticker,
          message: `${pos.ticker}: +${actualRetPct.toFixed(1)}% vs target +${expectedRetPct.toFixed(0)}% (consider taking profit)`,
          severity: "green",
        });
      }
    }

    // Stop loss proximity
    if (pos.stop_loss != null && pos.avg_cost > 0) {
      const stopLossPct = ((pos.stop_loss - pos.avg_cost) / pos.avg_cost) * 100;
      const actualPnlPct = pos.unrealized_pnl_pct * 100;
      if (actualPnlPct <= stopLossPct + 2 && actualPnlPct > stopLossPct) {
        alerts.push({
          ticker: pos.ticker,
          message: `${pos.ticker}: ${actualPnlPct.toFixed(1)}% (stop loss at ${stopLossPct.toFixed(1)}%)`,
          severity: "red",
        });
      } else if (actualPnlPct <= stopLossPct) {
        alerts.push({
          ticker: pos.ticker,
          message: `${pos.ticker}: ${actualPnlPct.toFixed(1)}% (below stop loss at ${stopLossPct.toFixed(1)}%)`,
          severity: "red",
        });
      }
    }
  }

  return alerts;
}

const severityColorMap: Record<string, string> = {
  red: "text-red-400",
  amber: "text-yellow-400",
  green: "text-emerald-400",
};

const severityDotMap: Record<string, string> = {
  red: "bg-red-400",
  amber: "bg-yellow-400",
  green: "bg-emerald-400",
};

export default function PortfolioPage() {
  usePageTitle("Portfolio");
  const [searchParams, setSearchParams] = useSearchParams();
  const addFormRef = useRef<HTMLDivElement>(null);
  const { data, loading, error, warnings, refetch } = useApi<Portfolio>(
    () => getPortfolio(),
    { cacheKey: "portfolio:main", ttlMs: 30_000 },
  );
  const alertsApi = useApi<Alert[]>(
    () => getAlerts({ limit: 5 }),
    { cacheKey: "portfolio:alerts", ttlMs: 15_000 },
  );
  const historyApi = useApi<Position[]>(
    () => getPositionHistory(),
    { cacheKey: "portfolio:history", ttlMs: 60_000 },
  );
  const [adding, setAdding] = useState(false);
  const [breakdownMode, setBreakdownMode] = useState<BreakdownMode>("ticker");
  const [closingPosition, setClosingPosition] = useState<Position | null>(null);
  const [posTab, setPosTab] = useState<"open" | "closed">("open");

  // Read query params for pre-fill from Analyze -> Add flow
  const addInitialValues = useMemo<AddPositionInitialValues | undefined>(() => {
    if (searchParams.get("add") !== "1") return undefined;
    return {
      ticker: searchParams.get("ticker") ?? undefined,
      asset_type: searchParams.get("asset_type") ?? undefined,
      avg_cost: searchParams.get("avg_cost") ?? undefined,
    };
  }, [searchParams]);

  // Auto-scroll to the add form when arriving with ?add=1
  useEffect(() => {
    if (searchParams.get("add") === "1" && !loading && addFormRef.current) {
      addFormRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
      // Clear the query params so they don't persist on refetch
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, loading, setSearchParams]);

  // P&L computation
  const totalPnl = useMemo(() => {
    if (!data) return { pnl: 0, pnlPct: 0, invested: 0 };
    const positions = data.positions;
    const invested = positions.reduce((s, p) => s + p.cost_basis, 0);
    const pnl = positions.reduce((s, p) => s + p.unrealized_pnl, 0);
    const pnlPct = invested > 0 ? (pnl / invested) * 100 : 0;
    return { pnl, pnlPct, invested };
  }, [data]);

  // Thesis drift
  const thesisAlerts = useMemo(() => {
    if (!data) return [];
    return computeThesisDriftAlerts(data.positions);
  }, [data]);

  const hasAnyThesis = useMemo(() => {
    if (!data) return false;
    return data.positions.some(
      (pos) =>
        pos.expected_hold_days != null ||
        pos.expected_return_pct != null ||
        pos.stop_loss != null,
    );
  }, [data]);

  async function handleAdd(pos: {
    ticker: string;
    asset_type: string;
    quantity: number;
    avg_cost: number;
    entry_date: string;
    thesis_text?: string;
    expected_return_pct?: number;
    expected_hold_days?: number;
    target_price?: number;
    stop_loss?: number;
  }) {
    setAdding(true);
    try {
      await addPosition(pos);
      invalidateCache("dashboard");
      invalidateCache("portfolio");
      invalidateCache("perf");
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to add position");
      throw err;
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(ticker: string) {
    if (!confirm(`Remove ${ticker}?`)) return;
    try {
      await removePosition(ticker);
      invalidateCache("dashboard");
      invalidateCache("portfolio");
      invalidateCache("perf");
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to remove position");
    }
  }

  async function handleClose(data: {
    exit_price: number;
    exit_reason: string;
    exit_date?: string;
  }) {
    if (!closingPosition) return;
    await closePosition(closingPosition.ticker, data);
    setClosingPosition(null);
    invalidateCache("dashboard");
    invalidateCache("portfolio");
    invalidateCache("perf");
    refetch();
    historyApi.refetch();
  }

  // Realized P&L from closed positions
  const totalRealizedPnl = useMemo(() => {
    if (!historyApi.data) return 0;
    return historyApi.data.reduce((s, p) => s + (p.realized_pnl ?? 0), 0);
  }, [historyApi.data]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorAlert message={error} />;
  if (!data) return null;

  const pnlTrend = totalPnl.pnl >= 0 ? ("up" as const) : ("down" as const);
  const pnlSign = totalPnl.pnl >= 0 ? "+" : "";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Portfolio</h1>
      <WarningsBanner warnings={[...warnings, ...alertsApi.warnings]} />

      {/* ── Stat cards row ── */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
      </div>

      {/* ── Export actions ── */}
      <div className="flex gap-2">
        <a href="/api/export/portfolio/csv" download className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium text-gray-300 transition-colors">
          Export CSV
        </a>
        <a href="/api/export/trades/csv" download className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium text-gray-300 transition-colors">
          Trade Journal
        </a>
        <a href="/api/export/portfolio/report" download className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium text-gray-300 transition-colors">
          Full Report
        </a>
      </div>

      {/* ── Allocation + Thesis Check ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Allocation (3/5) */}
        <div className="lg:col-span-3 rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-300">
              {breakdownMode === "ticker" ? "Ticker Breakdown" : "Sector Breakdown"}
            </h2>
            <div className="flex rounded-md overflow-hidden border border-gray-700 text-xs">
              <button
                onClick={() => setBreakdownMode("ticker")}
                className={`px-2.5 py-1 transition-colors duration-150 ${breakdownMode === "ticker" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-200"}`}
              >
                Ticker
              </button>
              <button
                onClick={() => setBreakdownMode("sector")}
                className={`px-2.5 py-1 transition-colors duration-150 ${breakdownMode === "sector" ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-200"}`}
              >
                Sector
              </button>
            </div>
          </div>
          {(() => {
            const alloc = buildAllocations(data, breakdownMode);
            return Object.keys(alloc).length > 0 ? (
              <AllocationChart allocations={alloc} />
            ) : (
              <EmptyState message="No allocation data." />
            );
          })()}
        </div>

        {/* Thesis Check (2/5) */}
        <div className="lg:col-span-2 rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">
            Thesis Check
          </h2>
          {!hasAnyThesis ? (
            <p className="text-gray-500 text-sm">
              No thesis recorded. Add thesis when entering positions to track drift.
            </p>
          ) : thesisAlerts.length === 0 ? (
            <p className="text-gray-400 text-sm">
              All positions tracking within thesis parameters.
            </p>
          ) : (
            <ul className="space-y-2">
              {thesisAlerts.map((alert, i) => (
                <li key={`${alert.ticker}-${i}`} className="flex items-start gap-2 text-sm">
                  <span
                    className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${severityDotMap[alert.severity] ?? "bg-gray-500"}`}
                  />
                  <span className={severityColorMap[alert.severity] ?? "text-gray-400"}>
                    {alert.message}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* ── Positions (tabbed: Open / Closed) ── */}
      <div>
        <div className="flex items-center gap-1 mb-3">
          <button
            onClick={() => setPosTab("open")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${posTab === "open" ? "bg-blue-600 text-white" : "text-gray-400 hover:text-gray-200"}`}
          >
            Open ({data.positions.length})
          </button>
          <button
            onClick={() => setPosTab("closed")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${posTab === "closed" ? "bg-blue-600 text-white" : "text-gray-400 hover:text-gray-200"}`}
          >
            Closed ({historyApi.data?.length ?? 0})
          </button>
        </div>

        {posTab === "open" ? (
          data.positions.length === 0 ? (
            <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
              <EmptyState message="No positions yet. Add one below." />
            </div>
          ) : (
            <PositionsTable
              positions={data.positions}
              onRemove={handleRemove}
              onClose={setClosingPosition}
            />
          )
        ) : historyApi.data && historyApi.data.length > 0 ? (
          <ClosedPositionsTable positions={historyApi.data} />
        ) : (
          <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
            <EmptyState message="No closed positions yet." />
          </div>
        )}
      </div>

      {/* Close Position Modal */}
      {closingPosition && (
        <ClosePositionModal
          position={closingPosition}
          onClose={() => setClosingPosition(null)}
          onConfirm={handleClose}
        />
      )}

      {/* ── Add Position form ── */}
      <div ref={addFormRef} className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">
          Add Position
        </h2>
        <AddPositionForm onAdd={handleAdd} loading={adding} initialValues={addInitialValues} />
      </div>

      {/* ── Weekly Summary + Recent Alerts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <WeeklySummaryCard />

        <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">
            Recent Alerts
          </h2>
          {alertsApi.data && alertsApi.data.length > 0 ? (
            <DashboardAlertsList alerts={alertsApi.data} />
          ) : (
            <EmptyState message="No recent alerts." />
          )}
        </div>
      </div>
    </div>
  );
}
