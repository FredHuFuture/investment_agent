import DataTable, { type Column } from "../shared/DataTable";
import SignalBadge from "../shared/SignalBadge";
import PnlText from "../shared/PnlText";
import { formatDate, formatCurrency } from "../../lib/formatters";
import type { BacktestTrade } from "../../api/types";

export default function TradesTable({ trades }: { trades: BacktestTrade[] }) {
  const columns: Column<BacktestTrade>[] = [
    {
      key: "entry",
      header: "Entry",
      render: (r) => <span className="text-gray-400">{formatDate(r.entry_date)}</span>,
      sortValue: (r) => r.entry_date,
    },
    {
      key: "exit",
      header: "Exit",
      render: (r) => (
        <span className="text-gray-400">
          {r.exit_date ? formatDate(r.exit_date) : "Open"}
        </span>
      ),
    },
    {
      key: "signal",
      header: "Signal",
      render: (r) => <SignalBadge signal={r.signal} />,
    },
    {
      key: "entry_price",
      header: "Entry $",
      render: (r) => <span className="font-mono">{formatCurrency(r.entry_price)}</span>,
      sortValue: (r) => r.entry_price,
    },
    {
      key: "exit_price",
      header: "Exit $",
      render: (r) => (
        <span className="font-mono">
          {r.exit_price != null ? formatCurrency(r.exit_price) : "-"}
        </span>
      ),
    },
    {
      key: "pnl",
      header: "PnL",
      render: (r) =>
        r.pnl_pct != null ? <PnlText value={r.pnl_pct} /> : <span>-</span>,
      sortValue: (r) => r.pnl_pct ?? 0,
    },
    {
      key: "reason",
      header: "Exit Reason",
      render: (r) => (
        <span className="text-gray-500 text-xs">{r.exit_reason ?? "-"}</span>
      ),
    },
    {
      key: "days",
      header: "Days",
      render: (r) => r.holding_days ?? "-",
      sortValue: (r) => r.holding_days ?? 0,
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={trades}
      keyFn={(r) => `${r.entry_date}-${r.signal}-${r.entry_price}`}
    />
  );
}
