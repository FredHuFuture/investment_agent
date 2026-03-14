import { Link } from "react-router-dom";
import DataTable, { type Column } from "../shared/DataTable";
import { formatCurrency, formatDate } from "../../lib/formatters";
import type { Position } from "../../api/types";

interface Props {
  positions: Position[];
}

function pnlColor(v: number): string {
  if (v > 0) return "text-emerald-400";
  if (v < 0) return "text-red-400";
  return "text-gray-400";
}

export default function ClosedPositionsTable({ positions }: Props) {
  const columns: Column<Position>[] = [
    {
      key: "ticker",
      header: "Ticker",
      render: (r) => (
        <Link
          to={`/portfolio/${r.ticker}`}
          className="font-mono font-semibold text-white hover:text-blue-400 transition-colors"
        >
          {r.ticker}
        </Link>
      ),
      sortValue: (r) => r.ticker,
    },
    {
      key: "type",
      header: "Type",
      render: (r) => <span className="text-gray-400">{r.asset_type}</span>,
    },
    {
      key: "qty",
      header: "Qty",
      render: (r) => (
        <span className="text-gray-300">{r.quantity.toFixed(r.quantity < 1 ? 6 : 2)}</span>
      ),
      sortValue: (r) => r.quantity,
    },
    {
      key: "avg_cost",
      header: "Entry",
      render: (r) => (
        <span className="text-gray-300">{formatCurrency(r.avg_cost)}</span>
      ),
      sortValue: (r) => r.avg_cost,
    },
    {
      key: "exit_price",
      header: "Exit",
      render: (r) => (
        <span className="text-gray-300">
          {r.exit_price != null ? formatCurrency(r.exit_price) : "\u2014"}
        </span>
      ),
      sortValue: (r) => r.exit_price ?? 0,
    },
    {
      key: "realized_pnl",
      header: "P&L",
      render: (r) => {
        const pnl = r.realized_pnl ?? 0;
        return (
          <span className={`font-medium ${pnlColor(pnl)}`}>
            {pnl >= 0 ? "+" : ""}
            {formatCurrency(pnl)}
          </span>
        );
      },
      sortValue: (r) => r.realized_pnl ?? 0,
    },
    {
      key: "return_pct",
      header: "Return",
      render: (r) => {
        if (r.exit_price == null || r.avg_cost === 0) {
          return <span className="text-gray-500">{"\u2014"}</span>;
        }
        const ret = ((r.exit_price - r.avg_cost) / r.avg_cost) * 100;
        return (
          <span className={`font-medium ${pnlColor(ret)}`}>
            {ret >= 0 ? "+" : ""}
            {ret.toFixed(1)}%
          </span>
        );
      },
      sortValue: (r) =>
        r.exit_price != null && r.avg_cost > 0
          ? (r.exit_price - r.avg_cost) / r.avg_cost
          : 0,
    },
    {
      key: "reason",
      header: "Reason",
      render: (r) => (
        <span className="text-gray-400 capitalize">
          {r.exit_reason?.replace("_", " ") ?? "\u2014"}
        </span>
      ),
    },
    {
      key: "hold",
      header: "Held",
      render: (r) => {
        if (!r.entry_date || !r.exit_date) {
          return <span className="text-gray-500">{"\u2014"}</span>;
        }
        const days = Math.round(
          (new Date(r.exit_date).getTime() - new Date(r.entry_date).getTime()) /
            86400000,
        );
        return <span className="text-gray-400">{days}d</span>;
      },
      sortValue: (r) => {
        if (!r.entry_date || !r.exit_date) return 0;
        return (
          (new Date(r.exit_date).getTime() -
            new Date(r.entry_date).getTime()) /
          86400000
        );
      },
    },
    {
      key: "exit_date",
      header: "Closed",
      render: (r) => (
        <span className="text-gray-500">
          {r.exit_date ? formatDate(r.exit_date) : "\u2014"}
        </span>
      ),
      sortValue: (r) => r.exit_date ?? "",
    },
  ];

  return (
    <DataTable columns={columns} data={positions} keyFn={(r) => r.ticker} />
  );
}
