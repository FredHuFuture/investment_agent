import DataTable, { type Column } from "../shared/DataTable";
import PnlText from "../shared/PnlText";
import type { BatchRow } from "../../api/types";

export default function BatchResults({ rows }: { rows: BatchRow[] }) {
  const columns: Column<BatchRow>[] = [
    {
      key: "ticker",
      header: "Ticker",
      render: (r) => <span className="font-mono font-semibold">{r.ticker}</span>,
      sortValue: (r) => r.ticker,
    },
    {
      key: "agents",
      header: "Agents",
      render: (r) => <span className="text-gray-400 text-xs">{r.agents}</span>,
    },
    {
      key: "return",
      header: "Return",
      render: (r) => <PnlText value={r.metrics.total_return_pct} />,
      sortValue: (r) => r.metrics.total_return_pct,
    },
    {
      key: "sharpe",
      header: "Sharpe",
      render: (r) => <span className="font-mono">{r.metrics.sharpe_ratio.toFixed(2)}</span>,
      sortValue: (r) => r.metrics.sharpe_ratio,
    },
    {
      key: "maxdd",
      header: "Max DD",
      render: (r) => <PnlText value={r.metrics.max_drawdown_pct} />,
      sortValue: (r) => r.metrics.max_drawdown_pct,
    },
    {
      key: "winrate",
      header: "Win Rate",
      render: (r) => (
        <span className="font-mono">
          {(r.metrics.win_rate * 100).toFixed(1)}%
        </span>
      ),
      sortValue: (r) => r.metrics.win_rate,
    },
    {
      key: "trades",
      header: "Trades",
      render: (r) => r.metrics.total_trades,
      sortValue: (r) => r.metrics.total_trades,
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={rows}
      keyFn={(r) => `${r.ticker}-${r.agents}`}
    />
  );
}
