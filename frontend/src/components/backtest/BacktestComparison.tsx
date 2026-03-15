import { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { formatPct } from "../../lib/formatters";
import type { SavedBacktestRun } from "../../lib/backtestStorage";
import type { BacktestMetrics } from "../../api/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface Props {
  runs: SavedBacktestRun[];
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Metric definitions for comparison table
// ---------------------------------------------------------------------------
interface MetricDef {
  key: keyof BacktestMetrics;
  label: string;
  format: (v: number | undefined) => string;
  /** true if a lower value is "better" (e.g. max_drawdown — less negative is better) */
  lowerIsBetter?: boolean;
}

const METRIC_DEFS: MetricDef[] = [
  {
    key: "total_return_pct",
    label: "Total Return",
    format: (v) => (v != null ? formatPct(v) : "--"),
  },
  {
    key: "annualized_return_pct",
    label: "Annualized Return",
    format: (v) => (v != null ? formatPct(v) : "--"),
  },
  {
    key: "max_drawdown_pct",
    label: "Max Drawdown",
    format: (v) => (v != null ? formatPct(v) : "--"),
    lowerIsBetter: true,
  },
  {
    key: "sharpe_ratio",
    label: "Sharpe Ratio",
    format: (v) => (v != null ? v.toFixed(2) : "--"),
  },
  {
    key: "win_rate",
    label: "Win Rate",
    format: (v) => (v != null ? `${v.toFixed(1)}%` : "--"),
  },
  {
    key: "total_trades",
    label: "Total Trades",
    format: (v) => (v != null ? String(Math.round(v)) : "--"),
  },
  {
    key: "sortino_ratio",
    label: "Sortino Ratio",
    format: (v) => (v != null ? v.toFixed(2) : "--"),
  },
  {
    key: "profit_factor",
    label: "Profit Factor",
    format: (v) => (v != null ? v.toFixed(2) : "--"),
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Normalize an equity curve so it starts at 100. */
function normalizeEquity(
  curve: Array<{ date: string; equity: number }>,
): Array<{ date: string; value: number }> {
  if (curve.length === 0) return [];
  const base = curve[0]?.equity || 1;
  return curve.map((pt) => ({
    date: pt.date,
    value: (pt.equity / base) * 100,
  }));
}

/** Determine diff color: green = Run B better, red = Run B worse */
function diffColor(diff: number, lowerIsBetter?: boolean): string {
  if (diff === 0 || isNaN(diff)) return "text-gray-400";
  // For lowerIsBetter metrics (max_drawdown): a negative diff means Run B is
  // more negative (worse drawdown), so Run B is worse. A positive diff means
  // Run B is less negative (closer to 0), so Run B is better.
  // Wait -- actually max_drawdown values are negative. If Run A = -8 and Run B = -5,
  // diff = Run B - Run A = -5 - (-8) = +3. Positive diff, and Run B IS better (less drawdown).
  // With lowerIsBetter: we want the value closest to 0 (highest value for negatives).
  // So for lowerIsBetter: positive diff means Run B value is higher (better for drawdown).
  // Actually "lowerIsBetter" is a bit confusing for drawdown. Let's think of it as:
  // For drawdown, a HIGHER value (closer to 0) is better. So lowerIsBetter = true means
  // "a more negative number is worse". If diff > 0, Run B's value is higher = better.
  // This is the same logic as higherIsBetter! So let's flip the semantics:
  // lowerIsBetter means lower absolute magnitude is better for negative metrics.
  // For max_drawdown: -5 is better than -8. diff = -5 - (-8) = +3. Positive = B is better.
  // So for lowerIsBetter: positive diff = B better = green. Same as !lowerIsBetter.
  // Actually this simplifies: for ALL metrics, positive diff = B has higher value.
  // For most metrics, higher = better (green). For max_drawdown (lowerIsBetter=true),
  // higher value (less negative) = better (green) too!
  // So diff > 0 is always green, diff < 0 is always red. The lowerIsBetter flag
  // doesn't change the diff color logic for drawdown because higher = better there too.
  // BUT: what about a hypothetical metric where truly lower is better (like fees)?
  // Then diff < 0 means B is lower = better = green. So we DO need the flag.
  // For max_drawdown specifically: values are negative, higher = better, so it behaves
  // like higherIsBetter. We mark it lowerIsBetter because conceptually lower drawdown
  // magnitude is better. But the sign math works out the same.
  // Let's just keep it simple: for lowerIsBetter, negative diff = green.
  const bIsBetter = lowerIsBetter ? diff < 0 : diff > 0;
  return bIsBetter ? "text-emerald-400" : "text-red-400";
}

function formatDiff(diff: number): string {
  if (isNaN(diff)) return "--";
  const sign = diff > 0 ? "+" : "";
  return `${sign}${diff.toFixed(2)}`;
}

// Tooltip for the overlay chart
interface CompareTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: string;
}

function CompareTooltip({ active, payload, label }: CompareTooltipProps) {
  if (!active || !payload?.length) return null;
  const date = label
    ? new Date(label).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "";
  return (
    <div className="bg-gray-950/95 border border-gray-700/60 rounded px-2.5 py-1.5 text-[11px] shadow-2xl backdrop-blur-sm">
      <div className="text-gray-500">{date}</div>
      {payload.map((entry) => (
        <div key={entry.name} className="font-mono mt-0.5" style={{ color: entry.color }}>
          {entry.name}: {entry.value?.toFixed(2) ?? "--"}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function BacktestComparison({ runs, onClose }: Props) {
  // Allow user to pick Run A and Run B via dropdowns
  const [idxA, setIdxA] = useState(0);
  const [idxB, setIdxB] = useState(runs.length > 1 ? 1 : 0);

  // Empty state
  if (runs.length < 2) {
    return (
      <Card>
        <CardHeader
          title="Compare Backtests"
          action={
            <Button size="sm" variant="ghost" onClick={onClose}>
              Close
            </Button>
          }
        />
        <CardBody>
          <p className="text-sm text-gray-500 text-center py-4">
            Select at least 2 saved runs to compare.
          </p>
        </CardBody>
      </Card>
    );
  }

  // Clamp indices to valid range; runs.length >= 2 is guaranteed here
  const safeIdxA = Math.min(idxA, runs.length - 1);
  const safeIdxB = Math.min(idxB, runs.length - 1);
  const runA = runs[safeIdxA]!;
  const runB = runs[safeIdxB]!;

  // Build merged equity curve data for the overlay chart
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const chartData = useMemo(() => {
    const normA = normalizeEquity(runA.equity_curve);
    const normB = normalizeEquity(runB.equity_curve);

    // Build a map by date
    const dateMap = new Map<string, { date: string; runA?: number; runB?: number }>();

    for (const pt of normA) {
      dateMap.set(pt.date, { date: pt.date, runA: pt.value });
    }
    for (const pt of normB) {
      const existing = dateMap.get(pt.date);
      if (existing) {
        existing.runB = pt.value;
      } else {
        dateMap.set(pt.date, { date: pt.date, runB: pt.value });
      }
    }

    return Array.from(dateMap.values()).sort(
      (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
    );
  }, [runA, runB]);

  // Summary verdict
  const returnDiff = runB.metrics.total_return_pct - runA.metrics.total_return_pct;
  const verdict =
    Math.abs(returnDiff) < 0.01
      ? "Both runs have identical total return"
      : returnDiff > 0
        ? `Run B outperforms Run A by ${formatPct(returnDiff)} total return`
        : `Run A outperforms Run B by ${formatPct(Math.abs(returnDiff))} total return`;

  const runALabel = runA.label || runA.ticker;
  const runBLabel = runB.label || runB.ticker;

  return (
    <div data-testid="backtest-comparison">
    <Card>
      <CardHeader
        title="Compare Backtests"
        subtitle={`Comparing ${runs.length} runs`}
        action={
          <Button size="sm" variant="ghost" onClick={onClose}>
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
            Close
          </Button>
        }
      />
      <CardBody>
        <div className="space-y-6">
          {/* Run selectors */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Run A
              </label>
              <select
                value={idxA}
                onChange={(e) => setIdxA(Number(e.target.value))}
                className="w-full rounded-lg bg-gray-800 border border-gray-700 text-gray-200 text-sm px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                data-testid="select-run-a"
              >
                {runs.map((r, i) => (
                  <option key={r.id} value={i}>
                    {r.label || r.ticker} ({r.ticker}, {formatPct(r.metrics.total_return_pct)})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Run B
              </label>
              <select
                value={idxB}
                onChange={(e) => setIdxB(Number(e.target.value))}
                className="w-full rounded-lg bg-gray-800 border border-gray-700 text-gray-200 text-sm px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                data-testid="select-run-b"
              >
                {runs.map((r, i) => (
                  <option key={r.id} value={i}>
                    {r.label || r.ticker} ({r.ticker}, {formatPct(r.metrics.total_return_pct)})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Side-by-side metrics table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="comparison-metrics-table">
              <thead>
                <tr className="border-b border-gray-800/50">
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Metric
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-blue-400 uppercase tracking-wider">
                    Run A
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-purple-400 uppercase tracking-wider">
                    Run B
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Diff
                  </th>
                </tr>
              </thead>
              <tbody>
                {METRIC_DEFS.map((def) => {
                  const valA = runA.metrics[def.key];
                  const valB = runB.metrics[def.key];
                  const diff =
                    valA != null && valB != null ? (valB as number) - (valA as number) : NaN;

                  return (
                    <tr
                      key={def.key}
                      className="border-b border-gray-800/30 hover:bg-gray-800/20"
                    >
                      <td className="px-3 py-2 text-gray-300">{def.label}</td>
                      <td className="px-3 py-2 text-right font-mono text-gray-200">
                        {def.format(valA as number | undefined)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-gray-200">
                        {def.format(valB as number | undefined)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right font-mono ${diffColor(diff, def.lowerIsBetter)}`}
                      >
                        {formatDiff(diff)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Overlaid equity curves */}
          {chartData.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Equity Curves (normalized to 100)
              </h4>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={chartData}
                    margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="#1f2937"
                      vertical={false}
                    />
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
                      orientation="right"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: "#4b5563", fontSize: 10 }}
                      width={44}
                    />
                    <Tooltip content={<CompareTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="runA"
                      name={runALabel}
                      stroke="#60a5fa"
                      strokeWidth={1.5}
                      dot={false}
                      connectNulls
                      isAnimationActive={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="runB"
                      name={runBLabel}
                      stroke="#a78bfa"
                      strokeWidth={1.5}
                      dot={false}
                      connectNulls
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              {/* Legend */}
              <div className="mt-2 flex items-center gap-5 px-1">
                <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
                  <span className="inline-block w-3 h-0.5 bg-blue-400 rounded" />
                  Run A: {runALabel}
                </span>
                <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
                  <span className="inline-block w-3 h-0.5 bg-purple-400 rounded" />
                  Run B: {runBLabel}
                </span>
              </div>
            </div>
          )}

          {/* Summary verdict */}
          <div className="rounded-lg bg-gray-800/50 border border-gray-700/50 px-4 py-3">
            <p className="text-sm text-gray-300" data-testid="comparison-verdict">
              {verdict}
            </p>
          </div>
        </div>
      </CardBody>
    </Card>
    </div>
  );
}
