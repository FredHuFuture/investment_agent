import { Link } from "react-router-dom";
import DataTable, { type Column } from "../shared/DataTable";
import { formatCurrency, formatNumber, formatDate } from "../../lib/formatters";
import type { Position } from "../../api/types";

interface Props {
  positions: Position[];
  onRemove: (ticker: string) => void;
  onClose?: (position: Position) => void;
}

function pnlColor(v: number): string {
  if (v > 0) return "text-emerald-400";
  if (v < 0) return "text-red-400";
  return "text-gray-400";
}

function holdColor(held: number, expected: number | null): string {
  if (expected == null) return "text-gray-400";
  const ratio = held / expected;
  if (ratio > 1.0) return "text-red-400";
  if (ratio >= 0.8) return "text-yellow-400";
  return "text-emerald-400";
}

export default function PositionsTable({ positions, onRemove, onClose }: Props) {
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
      render: (r) => <span className="text-gray-300">{formatNumber(r.quantity, r.quantity < 1 ? 6 : 2)}</span>,
      sortValue: (r) => r.quantity,
    },
    {
      key: "avg_cost",
      header: "Avg Cost",
      render: (r) => <span className="text-gray-300">{formatCurrency(r.avg_cost)}</span>,
      sortValue: (r) => r.avg_cost,
    },
    {
      key: "price",
      header: "Price",
      render: (r) =>
        r.current_price > 0 ? (
          <span className="text-gray-300">{formatCurrency(r.current_price)}</span>
        ) : (
          <span className="text-gray-500">{"\u2014"}</span>
        ),
      sortValue: (r) => r.current_price,
    },
    {
      key: "mkt_val",
      header: "Mkt Value",
      render: (r) => <span className="text-gray-200">{formatCurrency(r.market_value)}</span>,
      sortValue: (r) => r.market_value,
    },
    {
      key: "pnl",
      header: "P&L",
      render: (r) => (
        <span className={`font-medium ${pnlColor(r.unrealized_pnl)}`}>
          {r.unrealized_pnl > 0 ? "+" : ""}
          {formatCurrency(r.unrealized_pnl)}
        </span>
      ),
      sortValue: (r) => r.unrealized_pnl,
    },
    {
      key: "pnl_pct",
      header: "P&L %",
      render: (r) => (
        <span className={`font-medium ${pnlColor(r.unrealized_pnl_pct)}`}>
          {r.unrealized_pnl_pct > 0 ? "+" : ""}
          {(r.unrealized_pnl_pct * 100).toFixed(1)}%
        </span>
      ),
      sortValue: (r) => r.unrealized_pnl_pct,
    },
    {
      key: "hold",
      header: "Hold",
      render: (r) => {
        if (r.expected_hold_days == null) {
          return (
            <span className="text-gray-400">{r.holding_days}d</span>
          );
        }
        return (
          <span className={holdColor(r.holding_days, r.expected_hold_days)}>
            {r.holding_days}/{r.expected_hold_days}d
          </span>
        );
      },
      sortValue: (r) => r.holding_days,
    },
    {
      key: "entry",
      header: "Entry",
      render: (r) => <span className="text-gray-500">{formatDate(r.entry_date)}</span>,
      sortValue: (r) => r.entry_date,
    },
    {
      key: "actions",
      header: "",
      render: (r) => (
        <div className="flex gap-2">
          {onClose && (
            <button
              onClick={() => onClose(r)}
              className="text-yellow-400/70 hover:text-yellow-300 text-xs transition-colors duration-150"
            >
              Close
            </button>
          )}
          <button
            onClick={() => onRemove(r.ticker)}
            className="text-red-400/70 hover:text-red-300 text-xs transition-colors duration-150"
          >
            Remove
          </button>
        </div>
      ),
    },
  ];

  return <DataTable columns={columns} data={positions} keyFn={(r) => r.ticker} />;
}
