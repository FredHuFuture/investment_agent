import MetricCard from "../shared/MetricCard";
import EquityCurveChart from "./EquityCurveChart";
import TradesTable from "./TradesTable";
import { formatPct } from "../../lib/formatters";
import type { BacktestResult } from "../../api/types";

export default function BacktestResults({ data }: { data: BacktestResult }) {
  const m = data.metrics;
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
