import { useState } from "react";
import MetricCard from "../shared/MetricCard";
import EquityCurveChart from "./EquityCurveChart";
import TradesTable from "./TradesTable";
import { formatPct } from "../../lib/formatters";
import type { BacktestResult } from "../../api/types";

export default function BacktestResults({ data }: { data: BacktestResult }) {
  const m = data.metrics;
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Build list of advanced metrics that are defined
  const advancedMetrics: Array<{
    label: string;
    value: string;
    trend?: "up" | "down";
  }> = [];

  if (m.sortino_ratio != null) {
    advancedMetrics.push({
      label: "Sortino Ratio",
      value: m.sortino_ratio.toFixed(2),
    });
  }
  if (m.calmar_ratio != null) {
    advancedMetrics.push({
      label: "Calmar Ratio",
      value: m.calmar_ratio.toFixed(2),
    });
  }
  if (m.profit_factor != null) {
    advancedMetrics.push({
      label: "Profit Factor",
      value: m.profit_factor.toFixed(2),
      trend: m.profit_factor >= 1 ? "up" : "down",
    });
  }
  if (m.avg_win_pct != null) {
    advancedMetrics.push({
      label: "Avg Win",
      value: formatPct(m.avg_win_pct),
      trend: "up",
    });
  }
  if (m.avg_loss_pct != null) {
    advancedMetrics.push({
      label: "Avg Loss",
      value: formatPct(m.avg_loss_pct),
      trend: "down",
    });
  }
  if (m.avg_holding_days != null) {
    advancedMetrics.push({
      label: "Avg Holding Days",
      value: `${Math.round(m.avg_holding_days)}d`,
    });
  }
  if (m.max_consecutive_wins != null) {
    advancedMetrics.push({
      label: "Max Consecutive Wins",
      value: String(m.max_consecutive_wins),
      trend: "up",
    });
  }
  if (m.max_consecutive_losses != null) {
    advancedMetrics.push({
      label: "Max Consecutive Losses",
      value: String(m.max_consecutive_losses),
      trend: "down",
    });
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Return"
          value={formatPct(m.total_return_pct)}
        />
        <MetricCard
          label="Annualized"
          value={formatPct(m.annualized_return_pct)}
        />
        <MetricCard
          label="Max Drawdown"
          value={formatPct(m.max_drawdown_pct)}
        />
        <MetricCard
          label="Sharpe"
          value={m.sharpe_ratio.toFixed(2)}
        />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Win Rate" value={`${m.win_rate.toFixed(1)}%`} />
        <MetricCard label="Total Trades" value={String(m.total_trades)} />
      </div>

      {/* Advanced Metrics Section */}
      {advancedMetrics.length > 0 && (
        <>
          <div className="border-t border-gray-800/50" />
          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="flex items-center gap-2 text-sm font-medium text-gray-400 hover:text-gray-200 transition-colors"
              data-testid="toggle-advanced-metrics"
            >
              <svg
                className={`h-4 w-4 transition-transform ${showAdvanced ? "rotate-90" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="m8.25 4.5 7.5 7.5-7.5 7.5"
                />
              </svg>
              {showAdvanced ? "Hide Advanced Metrics" : "Show Advanced Metrics"}
            </button>
            {showAdvanced && (
              <div
                className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4"
                data-testid="advanced-metrics-panel"
              >
                {advancedMetrics.map((metric) => (
                  <MetricCard
                    key={metric.label}
                    label={metric.label}
                    value={metric.value}
                    trend={metric.trend}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}

      <div className="rounded-xl bg-gray-900/50 backdrop-blur-sm border border-gray-800/50 p-5">
        <h3 className="text-sm font-semibold text-gray-400 mb-3">
          Equity Curve
        </h3>
        <EquityCurveChart
          data={data.equity_curve}
          signalsLog={data.signals_log}
          initialCapital={data.equity_curve[0]?.equity ?? 100000}
        />
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 mb-3">
          Trade Log ({data.trades_count} trades)
        </h3>
        <TradesTable trades={data.trades} />
      </div>
    </div>
  );
}
