import DataTable, { type Column } from "../shared/DataTable";
import type { AgentPerformanceEntry } from "../../api/types";

export default function AgentPerformance({
  data,
}: {
  data: AgentPerformanceEntry[];
}) {
  const columns: Column<AgentPerformanceEntry>[] = [
    {
      key: "agent",
      header: "Agent",
      render: (r) => <span className="font-semibold">{r.agent}</span>,
    },
    {
      key: "signals",
      header: "Signals",
      render: (r) => r.total_signals,
      sortValue: (r) => r.total_signals,
    },
    {
      key: "accuracy",
      header: "Dir. Accuracy",
      render: (r) => (
        <span className="font-mono">{r.directional_accuracy_pct.toFixed(1)}%</span>
      ),
      sortValue: (r) => r.directional_accuracy_pct,
    },
    {
      key: "agreement",
      header: "Agreement",
      render: (r) => (
        <span className="font-mono">{r.agreement_rate_pct.toFixed(1)}%</span>
      ),
      sortValue: (r) => r.agreement_rate_pct,
    },
    {
      key: "confidence",
      header: "Avg Confidence",
      render: (r) => (
        <span className="font-mono">{(r.avg_confidence * 100).toFixed(0)}%</span>
      ),
      sortValue: (r) => r.avg_confidence,
    },
  ];

  return <DataTable columns={columns} data={data} keyFn={(r) => r.agent} />;
}
