import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import {
  getPortfolioGoals,
  addPortfolioGoal,
  deletePortfolioGoal,
} from "../../api/endpoints";
import type { PortfolioGoal } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import EmptyState from "../shared/EmptyState";
import { useToast } from "../../contexts/ToastContext";
import { formatCurrency } from "../../lib/formatters";

interface GoalTrackerProps {
  currentValue: number;
}

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T00:00:00");
  const now = new Date();
  const diff = target.getTime() - now.getTime();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

export default function GoalTracker({ currentValue }: GoalTrackerProps) {
  const api = useApi<PortfolioGoal[]>(() => getPortfolioGoals(), {
    cacheKey: "portfolio:goals",
    ttlMs: 30_000,
  });
  const { toast } = useToast();

  const [label, setLabel] = useState("");
  const [targetValue, setTargetValue] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const tv = parseFloat(targetValue);
    if (!label.trim()) {
      toast.error("Missing label", "Goal label is required.");
      return;
    }
    if (isNaN(tv) || tv <= 0) {
      toast.error("Invalid target", "Target value must be a positive number.");
      return;
    }

    setSubmitting(true);
    try {
      await addPortfolioGoal({
        label: label.trim(),
        target_value: tv,
        target_date: targetDate || undefined,
      });
      toast.success("Goal added", label.trim());
      setLabel("");
      setTargetValue("");
      setTargetDate("");
      api.refetch();
    } catch (err) {
      toast.error(
        "Failed to add goal",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(goal: PortfolioGoal) {
    setDeletingId(goal.id);
    try {
      await deletePortfolioGoal(goal.id);
      toast.success("Goal removed", goal.label);
      api.refetch();
    } catch (err) {
      toast.error(
        "Failed to remove goal",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <Card>
      <CardHeader title="Portfolio Goals" />
      <CardBody>
        {api.loading && !api.data && (
          <div className="space-y-3">
            <Skeleton variant="text" width="50%" height={14} />
            <Skeleton variant="rectangular" height={80} />
          </div>
        )}

        {api.error && !api.data && (
          <p className="text-gray-500 text-sm">
            Could not load goals.
          </p>
        )}

        {api.data && (
          <div className="space-y-4">
            {api.data.length === 0 ? (
              <EmptyState message="No goals set yet. Add one below." />
            ) : (
              <div className="space-y-3">
                {api.data.map((goal) => {
                  const progress = Math.min(
                    (currentValue / goal.target_value) * 100,
                    100,
                  );
                  const remaining = goal.target_date
                    ? daysUntil(goal.target_date)
                    : null;

                  return (
                    <div
                      key={goal.id}
                      className="rounded-lg bg-gray-800/40 border border-gray-700/40 p-4"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h4 className="text-sm font-medium text-gray-200">
                            {goal.label}
                          </h4>
                          <p className="text-xs text-gray-500 mt-0.5">
                            Target: {formatCurrency(goal.target_value)}
                            {goal.target_date && (
                              <span className="ml-2">
                                {remaining !== null && remaining >= 0
                                  ? `${remaining}d remaining`
                                  : remaining !== null
                                    ? "Past due"
                                    : ""}
                              </span>
                            )}
                          </p>
                        </div>
                        <button
                          onClick={() => handleDelete(goal)}
                          disabled={deletingId === goal.id}
                          className="text-gray-600 hover:text-red-400 transition-colors disabled:opacity-50"
                          title="Remove goal"
                        >
                          <svg
                            className="w-4 h-4"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={2}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M18 6L6 18M6 6l12 12" />
                          </svg>
                        </button>
                      </div>

                      {/* Progress bar */}
                      <div className="w-full bg-gray-700/50 rounded-full h-2 mb-1.5">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            progress >= 100
                              ? "bg-emerald-500"
                              : progress >= 75
                                ? "bg-blue-500"
                                : progress >= 50
                                  ? "bg-yellow-500"
                                  : "bg-gray-500"
                          }`}
                          style={{ width: `${progress}%` }}
                        />
                      </div>

                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-400">
                          {formatCurrency(currentValue)} of{" "}
                          {formatCurrency(goal.target_value)}
                        </span>
                        <span
                          className={`font-mono font-medium ${
                            progress >= 100
                              ? "text-emerald-400"
                              : "text-gray-300"
                          }`}
                        >
                          {progress.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Add goal form */}
            <form
              onSubmit={handleSubmit}
              className="pt-3 border-t border-gray-800/50"
            >
              <div className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold mb-2">
                Add Goal
              </div>
              <div className="flex flex-wrap items-end gap-3">
                <div className="flex flex-col">
                  <label
                    htmlFor="goal-label"
                    className="text-[10px] text-gray-500 mb-1"
                  >
                    Label
                  </label>
                  <input
                    id="goal-label"
                    type="text"
                    placeholder="Retirement Fund"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    className="w-44 rounded-md bg-gray-800/60 border border-gray-700/50 px-2.5 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500/50"
                    required
                  />
                </div>
                <div className="flex flex-col">
                  <label
                    htmlFor="goal-target"
                    className="text-[10px] text-gray-500 mb-1"
                  >
                    Target Value
                  </label>
                  <input
                    id="goal-target"
                    type="number"
                    step="any"
                    min="0"
                    placeholder="100000"
                    value={targetValue}
                    onChange={(e) => setTargetValue(e.target.value)}
                    className="w-32 rounded-md bg-gray-800/60 border border-gray-700/50 px-2.5 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500/50"
                    required
                  />
                </div>
                <div className="flex flex-col">
                  <label
                    htmlFor="goal-date"
                    className="text-[10px] text-gray-500 mb-1"
                  >
                    Target Date
                  </label>
                  <input
                    id="goal-date"
                    type="date"
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                    className="w-36 rounded-md bg-gray-800/60 border border-gray-700/50 px-2.5 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500/50"
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {submitting ? "Adding..." : "Add Goal"}
                </button>
              </div>
            </form>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
