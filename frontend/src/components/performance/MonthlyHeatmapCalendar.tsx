import { useApi } from "../../hooks/useApi";
import { getMonthlyHeatmap } from "../../api/endpoints";
import type { MonthlyHeatmapCell } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function getCellColor(returnPct: number | null): string {
  if (returnPct == null) return "bg-gray-800/40 text-gray-600";
  if (returnPct > 5) return "bg-green-600/70 text-green-100";
  if (returnPct > 2) return "bg-green-600/50 text-green-200";
  if (returnPct > 0) return "bg-green-600/30 text-green-300";
  if (returnPct === 0) return "bg-gray-700/50 text-gray-400";
  if (returnPct > -2) return "bg-red-600/30 text-red-300";
  if (returnPct > -5) return "bg-red-600/50 text-red-200";
  return "bg-red-600/70 text-red-100";
}

export default function MonthlyHeatmapCalendar() {
  const { data, loading, error, refetch } = useApi<MonthlyHeatmapCell[]>(
    () => getMonthlyHeatmap(),
    { cacheKey: "perf:monthlyHeatmap", ttlMs: 120_000 },
  );

  if (loading) return <SkeletonCard className="h-[240px]" />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  const cells = data ?? [];

  if (cells.length === 0) {
    return (
      <Card>
        <CardHeader title="Monthly Returns Heatmap" />
        <CardBody>
          <EmptyState message="No monthly return data available." />
        </CardBody>
      </Card>
    );
  }

  // Build lookup: year -> month -> return_pct
  const lookup = new Map<number, Map<number, number>>();
  for (const cell of cells) {
    if (!lookup.has(cell.year)) {
      lookup.set(cell.year, new Map());
    }
    lookup.get(cell.year)!.set(cell.month, cell.return_pct);
  }

  const years = Array.from(lookup.keys()).sort();

  return (
    <Card>
      <CardHeader title="Monthly Returns Heatmap" subtitle="Return % by month" />
      <CardBody>
        <div className="overflow-x-auto">
          {/* Header row */}
          <div className="grid gap-1" style={{ gridTemplateColumns: `60px repeat(12, minmax(48px, 1fr))` }}>
            <div className="text-xs text-gray-500 font-medium py-1" />
            {MONTH_LABELS.map((m) => (
              <div key={m} className="text-xs text-gray-500 font-medium text-center py-1">
                {m}
              </div>
            ))}

            {/* Data rows */}
            {years.map((year) => {
              const yearData = lookup.get(year)!;
              return (
                <div key={year} className="contents">
                  <div className="text-xs text-gray-400 font-mono font-medium flex items-center">
                    {year}
                  </div>
                  {Array.from({ length: 12 }, (_, i) => {
                    const month = i + 1;
                    const val = yearData.get(month) ?? null;
                    const colorClass = getCellColor(val);
                    return (
                      <div
                        key={month}
                        className={`rounded text-center text-xs font-medium py-2 px-1 ${colorClass}`}
                        title={val != null ? `${year}-${String(month).padStart(2, "0")}: ${val.toFixed(2)}%` : "No data"}
                      >
                        {val != null ? `${val >= 0 ? "+" : ""}${val.toFixed(1)}%` : "--"}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
