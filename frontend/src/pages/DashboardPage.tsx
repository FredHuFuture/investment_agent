import { useState, useMemo } from "react";
import { useApi } from "../hooks/useApi";
import { getPortfolio, getAlerts, getDaemonStatus } from "../api/endpoints";
import type { Portfolio, Alert, DaemonStatus, Position } from "../api/types";
import MetricCard from "../components/shared/MetricCard";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import WarningsBanner from "../components/shared/WarningsBanner";
import AllocationChart from "../components/portfolio/AllocationChart";
import DashboardAlertsList from "../components/monitoring/DashboardAlertsList";
import WeeklySummaryCard from "../components/summary/WeeklySummaryCard";
import { formatCurrency } from "../lib/formatters";

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
// Thesis drift alert computation
// ---------------------------------------------------------------------------
interface ThesisDriftAlert {
  ticker: string;
  message: string;
  severity: "green" | "amber" | "red";
}

function computeThesisDriftAlerts(positions: Position[]): ThesisDriftAlert[] {
  const alerts: ThesisDriftAlert[] = [];

  for (const pos of positions) {
    // Skip positions without any thesis data
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

    // Return exceeding target (>1.5x expected)
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

    // Return approaching stop loss (within 2% of stop loss level)
    if (pos.stop_loss != null && pos.avg_cost > 0) {
      const stopLossPct = ((pos.stop_loss - pos.avg_cost) / pos.avg_cost) * 100;
      const actualPnlPct = pos.unrealized_pnl_pct * 100;
      // stop_loss is typically below avg_cost, so stopLossPct is negative
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

export default function DashboardPage() {
  const portfolio = useApi<Portfolio>(() => getPortfolio());
  const alerts = useApi<Alert[]>(() => getAlerts({ limit: 5 }));
  const daemon = useApi<DaemonStatus>(() => getDaemonStatus());
  const [breakdownMode, setBreakdownMode] = useState<BreakdownMode>("ticker");

  const anyLoading = portfolio.loading || alerts.loading || daemon.loading;
  const anyError = portfolio.error || alerts.error || daemon.error;

  // Compute thesis drift alerts from position data
  const thesisAlerts = useMemo(() => {
    if (!portfolio.data) return [];
    return computeThesisDriftAlerts(portfolio.data.positions);
  }, [portfolio.data]);

  const hasAnyThesis = useMemo(() => {
    if (!portfolio.data) return false;
    return portfolio.data.positions.some(
      (pos) =>
        pos.expected_hold_days != null ||
        pos.expected_return_pct != null ||
        pos.stop_loss != null,
    );
  }, [portfolio.data]);

  if (anyLoading) return <LoadingSpinner />;
  if (anyError)
    return <ErrorAlert message={anyError} />;

  const p = portfolio.data;

  // Find the most recent daemon run across all jobs
  const daemonEntries = daemon.data ? Object.entries(daemon.data) : [];
  const lastRunEntry = daemonEntries
    .filter(([, v]) => v.last_run)
    .sort(([, a], [, b]) => (b.last_run ?? "").localeCompare(a.last_run ?? ""))[0];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      <WarningsBanner warnings={[...portfolio.warnings, ...alerts.warnings]} />

      {/* Stat cards row — 4-col grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Portfolio Value"
          value={p ? formatCurrency(p.total_value) : "-"}
        />
        <MetricCard
          label="Cash"
          value={p ? formatCurrency(p.cash) : "-"}
        />
        <MetricCard
          label="Positions"
          value={p ? String(p.positions.length) : "0"}
        />
        <MetricCard
          label="Daemon Status"
          value={
            lastRunEntry
              ? lastRunEntry[1].status
              : "Never run"
          }
          sub={lastRunEntry ? lastRunEntry[0] : undefined}
        />
      </div>

      {/* Middle row: Allocation + Thesis Check — 2-col */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Allocation — takes 3/5 width */}
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
          {p && (Object.keys(p.sector_breakdown).length > 0 || p.top_concentration.length > 0) ? (
            <AllocationChart allocations={buildAllocations(p, breakdownMode)} />
          ) : (
            <EmptyState message="No positions to chart." />
          )}
        </div>

        {/* Thesis Check — takes 2/5 width */}
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

      {/* Lower row: Weekly Summary + Recent Alerts — 2-col */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <WeeklySummaryCard />

        <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">
            Recent Alerts
          </h2>
          {alerts.data && alerts.data.length > 0 ? (
            <DashboardAlertsList alerts={alerts.data} />
          ) : (
            <EmptyState message="No recent alerts." />
          )}
        </div>
      </div>
    </div>
  );
}
