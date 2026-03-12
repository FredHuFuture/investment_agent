import DataTable, { type Column } from "../shared/DataTable";
import SignalBadge from "../shared/SignalBadge";
import { formatDate } from "../../lib/formatters";
import type { SignalHistoryEntry } from "../../api/types";

/** RISK_ON → "Risk On", RISK_OFF → "Risk Off" */
function formatRegime(regime: string | null): string {
  if (!regime) return "—";
  return regime
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

const REGIME_COLORS: Record<string, string> = {
  RISK_ON: "text-green-400",
  RISK_OFF: "text-red-400",
  NEUTRAL: "text-gray-400",
};

export default function SignalHistory({
  entries,
}: {
  entries: SignalHistoryEntry[];
}) {
  const columns: Column<SignalHistoryEntry>[] = [
    {
      key: "ticker",
      header: "Ticker",
      render: (r) => <span className="font-mono font-semibold">{r.ticker}</span>,
      sortValue: (r) => r.ticker,
    },
    {
      key: "signal",
      header: "Signal",
      render: (r) => <SignalBadge signal={r.final_signal} />,
    },
    {
      key: "confidence",
      header: "Confidence",
      render: (r) => (
        <span className="font-mono">{r.final_confidence.toFixed(0)}%</span>
      ),
      sortValue: (r) => r.final_confidence,
    },
    {
      key: "score",
      header: "Score",
      render: (r) => (
        <span className="font-mono">{r.raw_score.toFixed(3)}</span>
      ),
      sortValue: (r) => r.raw_score,
    },
    {
      key: "regime",
      header: "Regime",
      render: (r) => (
        <span className={`text-xs font-medium ${REGIME_COLORS[r.regime ?? ""] ?? "text-gray-500"}`}>
          {formatRegime(r.regime)}
        </span>
      ),
    },
    {
      key: "time",
      header: "Date",
      render: (r) => (
        <span className="text-gray-400">{formatDate(r.created_at)}</span>
      ),
      sortValue: (r) => r.created_at,
    },
  ];

  return (
    <DataTable columns={columns} data={entries} keyFn={(r) => r.id} />
  );
}
