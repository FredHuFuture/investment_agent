import DataTable, { type Column } from "../shared/DataTable";
import { severityBg } from "../../lib/colors";
import { formatDate } from "../../lib/formatters";
import type { Alert } from "../../api/types";

function formatAlertType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

/**
 * Compact alerts table for the dashboard -- drops the full MESSAGE column
 * (which is too wide for a half-width card) and shows only the essential
 * columns. Full details are available on the Monitoring page.
 */
export default function DashboardAlertsList({ alerts }: { alerts: Alert[] }) {
  const columns: Column<Alert>[] = [
    {
      key: "severity",
      header: "Severity",
      render: (r) => (
        <span
          className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
            severityBg[r.severity] ?? "bg-gray-700 text-gray-300"
          }`}
        >
          {r.severity}
        </span>
      ),
    },
    {
      key: "ticker",
      header: "Ticker",
      render: (r) => (
        <span className="font-mono">{r.ticker ?? "PORTFOLIO"}</span>
      ),
      sortValue: (r) => r.ticker ?? "",
    },
    {
      key: "type",
      header: "Type",
      render: (r) => <span className="text-gray-300 text-xs">{formatAlertType(r.alert_type)}</span>,
    },
    {
      key: "message",
      header: "Message",
      render: (r) => {
        const truncated =
          r.message.length > 40 ? r.message.slice(0, 40) + "\u2026" : r.message;
        return (
          <span
            className="text-gray-300 text-xs"
            title={r.message}
          >
            {truncated}
          </span>
        );
      },
    },
    {
      key: "time",
      header: "Time",
      render: (r) => (
        <span className="text-gray-500 text-xs whitespace-nowrap">
          {formatDate(r.created_at)}
        </span>
      ),
      sortValue: (r) => r.created_at,
    },
  ];

  return <DataTable columns={columns} data={alerts} keyFn={(r) => r.id} />;
}
