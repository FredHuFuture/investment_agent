import { Button } from "../ui/Button";

/** Ordered from most to least severe. Values match the API severity field. */
const severities = ["all", "CRITICAL", "HIGH", "WARNING", "LOW", "INFO"] as const;

const severityLabels: Record<string, string> = {
  all: "All",
  CRITICAL: "Critical",
  HIGH: "High",
  WARNING: "Warning",
  LOW: "Low",
  INFO: "Info",
};

interface SeverityFilterBarProps {
  selectedSeverity: string;
  onChange: (severity: string) => void;
  counts: Record<string, number>;
}

export default function SeverityFilterBar({
  selectedSeverity,
  onChange,
  counts,
}: SeverityFilterBarProps) {
  const total = Object.values(counts).reduce((sum, c) => sum + c, 0);

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {severities.map((sev) => {
        const count = sev === "all" ? total : (counts[sev] ?? 0);
        const isSelected = selectedSeverity === sev;
        const label = severityLabels[sev] ?? sev;

        return (
          <Button
            key={sev}
            variant={isSelected ? "primary" : "ghost"}
            size="sm"
            onClick={() => onChange(sev)}
            className="min-h-[32px]"
          >
            {label}
            <span className="ml-1 opacity-70">({count})</span>
          </Button>
        );
      })}
    </div>
  );
}
