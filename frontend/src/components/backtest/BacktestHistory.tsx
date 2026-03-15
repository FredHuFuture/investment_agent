import { useState, useCallback, useEffect } from "react";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import ConfirmModal from "../ui/ConfirmModal";
import { useToast } from "../../contexts/ToastContext";
import {
  listBacktestRuns,
  deleteBacktestRun,
  clearAllBacktestRuns,
  type SavedBacktestRun,
} from "../../lib/backtestStorage";
import { formatPct } from "../../lib/formatters";

interface Props {
  /** Trigger comparison view with selected runs. */
  onCompare: (runs: SavedBacktestRun[]) => void;
  /** Incremented externally when a new run is saved, so this component refreshes. */
  refreshKey?: number;
}

const MAX_COMPARE = 5;

export default function BacktestHistory({ onCompare, refreshKey }: Props) {
  const [runs, setRuns] = useState<SavedBacktestRun[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const { toast } = useToast();

  const reload = useCallback(() => {
    setRuns(listBacktestRuns());
  }, []);

  // Load on mount and whenever refreshKey changes
  useEffect(() => {
    reload();
  }, [reload, refreshKey]);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size >= MAX_COMPARE) {
          toast.warning("Limit reached", `You can compare up to ${MAX_COMPARE} runs`);
          return prev;
        }
        next.add(id);
      }
      return next;
    });
  }

  function handleDelete(id: string) {
    deleteBacktestRun(id);
    setSelected((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
    reload();
    toast.success("Deleted", "Run removed from history");
  }

  function handleClearAll() {
    clearAllBacktestRuns();
    setSelected(new Set());
    reload();
    setConfirmClearOpen(false);
    toast.success("Cleared", "All saved runs removed");
  }

  function handleCompare() {
    const selectedRuns = runs.filter((r) => selected.has(r.id));
    onCompare(selectedRuns);
  }

  function formatSavedDate(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  if (runs.length === 0) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-gray-500 text-center py-4">
            No saved backtest runs yet. Run a backtest and click "Save Result" to add one.
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader
          title="Saved Backtest Runs"
          subtitle={`${runs.length} run${runs.length === 1 ? "" : "s"} saved`}
          action={
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="primary"
                disabled={selected.size < 2}
                onClick={handleCompare}
              >
                Compare Selected ({selected.size})
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => setConfirmClearOpen(true)}
              >
                Clear All
              </Button>
            </div>
          }
        />
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800/50">
                  <th className="pl-4 pr-2 py-3 text-left w-10">
                    <span className="sr-only">Select</span>
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Ticker
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Label
                  </th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Saved
                  </th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Return
                  </th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sharpe
                  </th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Win Rate
                  </th>
                  <th className="px-3 py-3 w-10">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => {
                  const isSelected = selected.has(run.id);
                  return (
                    <tr
                      key={run.id}
                      className={`border-b border-gray-800/30 hover:bg-gray-800/30 transition-colors ${
                        isSelected ? "bg-blue-900/20" : ""
                      }`}
                    >
                      <td className="pl-4 pr-2 py-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(run.id)}
                          className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                          aria-label={`Select ${run.label || run.ticker}`}
                        />
                      </td>
                      <td className="px-3 py-3 font-medium text-gray-200">
                        {run.ticker}
                      </td>
                      <td className="px-3 py-3 text-gray-400 max-w-[160px] truncate">
                        {run.label || "Untitled"}
                      </td>
                      <td className="px-3 py-3 text-gray-500 text-xs whitespace-nowrap">
                        {formatSavedDate(run.saved_at)}
                      </td>
                      <td
                        className={`px-3 py-3 text-right font-mono ${
                          run.metrics.total_return_pct >= 0
                            ? "text-emerald-400"
                            : "text-red-400"
                        }`}
                      >
                        {formatPct(run.metrics.total_return_pct)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-gray-300">
                        {run.metrics.sharpe_ratio.toFixed(2)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-gray-300">
                        {run.metrics.win_rate.toFixed(1)}%
                      </td>
                      <td className="px-3 py-3">
                        <button
                          onClick={() => handleDelete(run.id)}
                          className="text-gray-600 hover:text-red-400 transition-colors p-1"
                          aria-label={`Delete ${run.label || run.ticker}`}
                          title="Delete run"
                        >
                          <svg
                            className="h-4 w-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={2}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
                            />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>

      <ConfirmModal
        open={confirmClearOpen}
        onClose={() => setConfirmClearOpen(false)}
        onConfirm={handleClearAll}
        title="Clear All Saved Runs"
        description="This will permanently delete all saved backtest runs from your history. This action cannot be undone."
        confirmLabel="Clear All"
        variant="danger"
      />
    </>
  );
}
