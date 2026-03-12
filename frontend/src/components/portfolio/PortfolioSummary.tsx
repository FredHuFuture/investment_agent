import MetricCard from "../shared/MetricCard";
import { formatCurrency } from "../../lib/formatters";
import type { Portfolio } from "../../api/types";

export default function PortfolioSummary({ data }: { data: Portfolio }) {
  const invested = data.positions.reduce((s, p) => s + p.cost_basis, 0);
  const totalPnl = data.positions.reduce((s, p) => s + p.unrealized_pnl, 0);
  const pnlPct = invested > 0 ? (totalPnl / invested) * 100 : 0;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <MetricCard
        label="Total Value"
        value={formatCurrency(data.total_value)}
      />
      <MetricCard label="Cash" value={formatCurrency(data.cash)} />
      <MetricCard
        label="Invested"
        value={formatCurrency(invested)}
        sub={`${data.positions.length} positions`}
      />
      <MetricCard
        label="Unrealized P&L"
        value={`${totalPnl >= 0 ? "+" : ""}${formatCurrency(totalPnl)}`}
        sub={`${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(1)}%`}
        trend={totalPnl > 0 ? "up" : totalPnl < 0 ? "down" : undefined}
      />
    </div>
  );
}
