import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { formatPct } from "../../lib/formatters";
import type { SavedBacktestRun } from "../../lib/backtestStorage";

interface Props {
  runs: SavedBacktestRun[];
  onClose: () => void;
}

// Metric definitions: key, label, formatter, and whether higher is better
interface MetricDef {
  key: string;
  label: string;
  format: (v: number | undefined) => string;
  higherIsBetter: boolean;
}

const METRICS: MetricDef[] = [
  {
    key: "total_return_pct",
    label: "Total Return",
    format: (v) => (v != null ? formatPct(v) : "--"),
    higherIsBetter: true,
  },
  {
    key: "annualized_return_pct",
    label: "Annualized Return",
    format: (v) => (v != null ? formatPct(v) : "--"),
    higherIsBetter: true,
  },
  {
    key: "max_drawdown_pct",
    label: "Max Drawdown",
    format: (v) => (v != null ? formatPct(v) : "--"),
    higherIsBetter: false, // Less negative is better; we compare absolute values
  },
  {
    key: "sharpe_ratio",
    label: "Sharpe Ratio",
    format: (v) => (v != null ? v.toFixed(2) : "--"),
    higherIsBetter: true,
  },
  {
    key: "win_rate",
    label: "Win Rate",
    format: (v) => (v != null ? `${v.toFixed(1)}%` : "--"),
    higherIsBetter: true,
  },
  {
    key: "total_trades",
    label: "Total Trades",
    format: (v) => (v != null ? String(Math.round(v)) : "--"),
    higherIsBetter: true,
  },
  {
    key: "profit_factor",
    label: "Profit Factor",
    format: (v) => (v != null ? v.toFixed(2) : "--"),
    higherIsBetter: true,
  },
  {
    key: "sortino_ratio",
    label: "Sortino Ratio",
    format: (v) => (v != null ? v.toFixed(2) : "--"),
    higherIsBetter: true,
  },
  {
    key: "calmar_ratio",
    label: "Calmar Ratio",
    format: (v) => (v != null ? v.toFixed(2) : "--"),
    higherIsBetter: true,
  },
];

function findBestIndex(
  values: (number | undefined)[],
  higherIsBetter: boolean,
  key: string,
): number {
  let bestIdx = -1;
  let bestVal: number | undefined;

  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v == null) continue;

    if (bestVal == null) {
      bestVal = v;
      bestIdx = i;
      continue;
    }

    // For max_drawdown_pct, less negative = better, so the "higher" value is better
    // The higherIsBetter flag handles this: max_drawdown is higherIsBetter=false
    // meaning the smallest (most negative) is worst, so we want the largest (least negative).
    // Actually for drawdown, the value is negative, and "higher is better" = false means
    // we want the value closest to 0 (the largest number). Let's handle it simply:
    if (key === "max_drawdown_pct") {
      // Drawdown is negative; best = closest to 0 = highest value
      if (v > bestVal) {
        bestVal = v;
        bestIdx = i;
      }
    } else if (higherIsBetter) {
      if (v > bestVal) {
        bestVal = v;
        bestIdx = i;
      }
    } else {
      if (v < bestVal) {
        bestVal = v;
        bestIdx = i;
      }
    }
  }

  return bestIdx;
}

export default function BacktestComparison({ runs, onClose }: Props) {
  if (runs.length === 0) return null;

  return (
    <Card>
      <CardHeader
        title="Backtest Comparison"
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
      <CardBody className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800/50">
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[140px]">
                  Metric
                </th>
                {runs.map((run) => (
                  <th
                    key={run.id}
                    className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider min-w-[120px]"
                  >
                    <div className="flex flex-col items-end gap-0.5">
                      <span className="text-gray-200 normal-case text-sm font-semibold">
                        {run.ticker}
                      </span>
                      <span className="text-gray-500 normal-case text-xs font-normal truncate max-w-[140px]">
                        {run.label || "Untitled"}
                      </span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Date range row */}
              <tr className="border-b border-gray-800/30">
                <td className="px-4 py-2.5 text-gray-500 text-xs">
                  Period
                </td>
                {runs.map((run) => (
                  <td
                    key={run.id}
                    className="px-4 py-2.5 text-right text-gray-500 text-xs whitespace-nowrap"
                  >
                    {run.params.start_date} to {run.params.end_date}
                  </td>
                ))}
              </tr>

              {/* Metric rows */}
              {METRICS.map((metric) => {
                const values = runs.map(
                  (r) => r.metrics[metric.key] as number | undefined,
                );

                // Skip row if ALL values are undefined
                if (values.every((v) => v == null)) return null;

                const bestIdx = findBestIndex(
                  values,
                  metric.higherIsBetter,
                  metric.key,
                );

                return (
                  <tr
                    key={metric.key}
                    className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors"
                  >
                    <td className="px-4 py-2.5 text-gray-400 font-medium">
                      {metric.label}
                    </td>
                    {runs.map((run, i) => {
                      const isBest = i === bestIdx && runs.length > 1;
                      return (
                        <td
                          key={run.id}
                          className={`px-4 py-2.5 text-right font-mono ${
                            isBest ? "text-emerald-400 font-semibold" : "text-gray-300"
                          }`}
                        >
                          {metric.format(values[i])}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardBody>
    </Card>
  );
}
