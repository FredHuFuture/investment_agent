import { useState, useCallback } from "react";
import { useApi } from "../../hooks/useApi";
import {
  getAlertRules,
  createAlertRule,
  deleteAlertRule,
  toggleAlertRule,
} from "../../api/endpoints";
import type { AlertRule } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";

const METRICS = [
  "drawdown_pct",
  "volatility",
  "var_95",
  "price_change_pct",
  "portfolio_value",
] as const;

const SEVERITIES = ["critical", "high", "medium", "low"] as const;
const CONDITIONS: Array<{ value: "gt" | "lt" | "eq"; label: string }> = [
  { value: "gt", label: ">" },
  { value: "lt", label: "<" },
  { value: "eq", label: "=" },
];

const SEVERITY_BADGE: Record<string, string> = {
  critical: "bg-red-900/60 text-red-300",
  high: "bg-orange-900/60 text-orange-300",
  medium: "bg-yellow-900/60 text-yellow-300",
  low: "bg-gray-700 text-gray-300",
};

const CONDITION_LABEL: Record<string, string> = {
  gt: ">",
  lt: "<",
  eq: "=",
};

export default function AlertRulesPanel() {
  const fetcher = useCallback(() => getAlertRules(), []);
  const { data, loading, error, refetch } = useApi<AlertRule[]>(fetcher, [], {
    cacheKey: "monitoring:alertRules",
    ttlMs: 15_000,
  });

  const [showForm, setShowForm] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [name, setName] = useState("");
  const [metric, setMetric] = useState<string>(METRICS[0]);
  const [condition, setCondition] = useState<"gt" | "lt" | "eq">("gt");
  const [threshold, setThreshold] = useState("");
  const [severity, setSeverity] = useState<string>("medium");

  function resetForm() {
    setName("");
    setMetric(METRICS[0]);
    setCondition("gt");
    setThreshold("");
    setSeverity("medium");
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !threshold) return;
    setFormLoading(true);
    try {
      await createAlertRule({
        name: name.trim(),
        metric,
        condition,
        threshold: Number(threshold),
        severity,
      });
      resetForm();
      setShowForm(false);
      refetch();
    } catch {
      // silently handle — user can retry
    } finally {
      setFormLoading(false);
    }
  }

  async function handleToggle(rule: AlertRule) {
    try {
      await toggleAlertRule(rule.id, !rule.enabled);
      refetch();
    } catch {
      // silently handle
    }
  }

  async function handleDelete(ruleId: number) {
    try {
      await deleteAlertRule(ruleId);
      refetch();
    } catch {
      // silently handle
    }
  }

  if (loading) return <SkeletonCard />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  return (
    <Card>
      <CardHeader
        title="Alert Rules"
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowForm((v) => !v)}
          >
            {showForm ? "Cancel" : "+ New Rule"}
          </Button>
        }
      />
      <CardBody>
        {/* Create rule form */}
        {showForm && (
          <form
            onSubmit={handleCreate}
            className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 items-end"
          >
            <div className="lg:col-span-2">
              <label className="block text-xs text-gray-500 mb-1">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Rule name"
                required
                className="w-full rounded-lg bg-gray-800 border border-gray-700 text-gray-200 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Metric</label>
              <select
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
                className="w-full rounded-lg bg-gray-800 border border-gray-700 text-gray-200 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent"
              >
                {METRICS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Condition
              </label>
              <select
                value={condition}
                onChange={(e) =>
                  setCondition(e.target.value as "gt" | "lt" | "eq")
                }
                className="w-full rounded-lg bg-gray-800 border border-gray-700 text-gray-200 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent"
              >
                {CONDITIONS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Threshold
              </label>
              <input
                type="number"
                step="any"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                placeholder="0"
                required
                className="w-full rounded-lg bg-gray-800 border border-gray-700 text-gray-200 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>
            <div className="sm:col-span-2 lg:col-span-1">
              <label className="block text-xs text-gray-500 mb-1">
                Severity
              </label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                className="w-full rounded-lg bg-gray-800 border border-gray-700 text-gray-200 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-accent"
              >
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2 lg:col-span-6 flex justify-end">
              <Button
                type="submit"
                variant="primary"
                size="sm"
                loading={formLoading}
              >
                Create Rule
              </Button>
            </div>
          </form>
        )}

        {/* Rules table */}
        {!data || data.length === 0 ? (
          <EmptyState message="No alert rules configured." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm table-auto">
              <thead>
                <tr className="border-b border-gray-800/50 text-left">
                  <th className="px-3 py-2.5 text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                    Name
                  </th>
                  <th className="px-3 py-2.5 text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                    Metric
                  </th>
                  <th className="px-3 py-2.5 text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                    Condition
                  </th>
                  <th className="px-3 py-2.5 text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                    Threshold
                  </th>
                  <th className="px-3 py-2.5 text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                    Severity
                  </th>
                  <th className="px-3 py-2.5 text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                    Enabled
                  </th>
                  <th className="px-3 py-2.5 text-right text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {[...data]
                  .sort((a, b) =>
                    (a.metric === "hardcoded" ? 0 : 1) -
                    (b.metric === "hardcoded" ? 0 : 1),
                  )
                  .map((rule) => {
                    const isBuiltin = rule.metric === "hardcoded";
                    return (
                      <tr
                        key={rule.id}
                        className="border-b border-gray-800/30 hover:bg-gray-800/40 transition-colors"
                      >
                        <td className="px-3 py-2.5 text-gray-200">
                          <span className="flex items-center gap-2 flex-wrap">
                            {rule.name}
                            {isBuiltin && (
                              <span
                                data-testid={`alert-rule-builtin-badge-${rule.id}`}
                                className="ml-1 text-[10px] uppercase tracking-wider text-gray-500 bg-gray-800 rounded px-1.5 py-0.5"
                              >
                                Built-in
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-gray-400 font-mono text-xs">
                          {isBuiltin ? (
                            <span className="text-xs text-gray-500">Built-in</span>
                          ) : (
                            rule.metric
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-gray-400">
                          {isBuiltin ? (
                            <span className="text-gray-600">&mdash;</span>
                          ) : (
                            CONDITION_LABEL[rule.condition] ?? rule.condition
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-gray-300 font-mono">
                          {isBuiltin ? (
                            <span className="text-gray-600">&mdash;</span>
                          ) : (
                            rule.threshold
                          )}
                        </td>
                        <td className="px-3 py-2.5">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
                              SEVERITY_BADGE[rule.severity] ??
                              "bg-gray-700 text-gray-300"
                            }`}
                          >
                            {rule.severity}
                          </span>
                        </td>
                        <td className="px-3 py-2.5">
                          <button
                            data-testid={`alert-rule-toggle-${rule.id}`}
                            onClick={() => handleToggle(rule)}
                            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                              rule.enabled ? "bg-accent" : "bg-gray-700"
                            }`}
                            title={rule.enabled ? "Disable rule" : "Enable rule"}
                          >
                            <span
                              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                                rule.enabled ? "translate-x-4" : "translate-x-1"
                              }`}
                            />
                          </button>
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          {!isBuiltin && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-400 hover:text-red-300 hover:bg-red-900/30"
                              onClick={() => handleDelete(rule.id)}
                              title="Delete rule"
                            >
                              &times;
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
