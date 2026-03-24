import type { Alert } from "../../api/types";

const severityConfig: Record<string, { bg: string; text: string; label: string }> = {
  CRITICAL: { bg: "bg-red-500/20", text: "text-red-400", label: "Critical" },
  HIGH: { bg: "bg-orange-500/20", text: "text-orange-400", label: "High" },
  WARNING: { bg: "bg-yellow-500/20", text: "text-yellow-400", label: "Warning" },
  LOW: { bg: "bg-gray-500/20", text: "text-gray-400", label: "Low" },
  INFO: { bg: "bg-accent/20", text: "text-accent-light", label: "Info" },
};

const severityOrder = ["CRITICAL", "HIGH", "WARNING", "LOW", "INFO"];

interface AlertSummaryChipsProps {
  alerts: Alert[];
}

export default function AlertSummaryChips({ alerts }: AlertSummaryChipsProps) {
  // Count alerts by severity
  const counts: Record<string, number> = {};
  for (const a of alerts) {
    const sev = a.severity.toUpperCase();
    counts[sev] = (counts[sev] ?? 0) + 1;
  }

  // Only show severities that have alerts, ordered by priority
  const activeSeverities = severityOrder.filter((s) => (counts[s] ?? 0) > 0);

  if (activeSeverities.length === 0) return null;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {activeSeverities.map((sev) => {
        const config = severityConfig[sev] ?? {
          bg: "bg-gray-500/20",
          text: "text-gray-400",
          label: sev,
        };
        return (
          <span
            key={sev}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${config.bg} ${config.text}`}
          >
            {counts[sev]} {config.label}
          </span>
        );
      })}
    </div>
  );
}
