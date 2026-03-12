import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { getPortfolio, addPosition, removePosition } from "../api/endpoints";
import type { Portfolio } from "../api/types";
import PortfolioSummary from "../components/portfolio/PortfolioSummary";
import PositionsTable from "../components/portfolio/PositionsTable";
import AddPositionForm from "../components/portfolio/AddPositionForm";
import AllocationChart from "../components/portfolio/AllocationChart";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import WarningsBanner from "../components/shared/WarningsBanner";

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

export default function PortfolioPage() {
  const { data, loading, error, warnings, refetch } = useApi<Portfolio>(
    () => getPortfolio(),
  );
  const [adding, setAdding] = useState(false);
  const [breakdownMode, setBreakdownMode] = useState<BreakdownMode>("sector");

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
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to remove position");
    }
  }

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorAlert message={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Portfolio</h1>
      <WarningsBanner warnings={warnings} />
      <PortfolioSummary data={data} />

      {/* Positions table (2/3) + Allocation chart (1/3) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 min-w-0">
          {data.positions.length === 0 ? (
            <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
              <EmptyState message="No positions yet. Add one below." />
            </div>
          ) : (
            <PositionsTable positions={data.positions} onRemove={handleRemove} />
          )}
        </div>
        <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
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
      </div>

      {/* Add Position form */}
      <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">
          Add Position
        </h2>
        <AddPositionForm onAdd={handleAdd} loading={adding} />
      </div>
    </div>
  );
}
