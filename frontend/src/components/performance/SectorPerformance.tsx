import { useApi } from "../../hooks/useApi";
import { getSectorPerformance } from "../../api/endpoints";
import type { SectorPerformanceEntry } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";
import { formatCurrency } from "../../lib/formatters";

export default function SectorPerformance() {
  const { data, loading, error, refetch } = useApi<SectorPerformanceEntry[]>(
    () => getSectorPerformance(),
    { cacheKey: "perf:sectorPerformance", ttlMs: 60_000 },
  );

  if (loading) return <SkeletonCard className="h-[340px]" />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  const entries = data ?? [];
  const maxAbsPnl = Math.max(...entries.map((e) => Math.abs(e.total_pnl)), 1);

  return (
    <Card>
      <CardHeader
        title="Sector Performance"
        subtitle="Aggregate P&L by sector across open and closed positions"
      />
      <CardBody>
        {entries.length === 0 ? (
          <EmptyState message="No positions to aggregate by sector." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800/50">
                  <th className="text-left py-2 pr-4">Sector</th>
                  <th className="text-right py-2 px-4">Total P&L</th>
                  <th className="text-right py-2 px-4">P&L %</th>
                  <th className="text-right py-2 px-4">Positions</th>
                  <th className="text-left py-2 px-4">Best</th>
                  <th className="text-left py-2 px-4">Worst</th>
                  <th className="py-2 pl-4 w-32">Contribution</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => {
                  const barWidth =
                    Math.abs(entry.total_pnl) / maxAbsPnl * 100;
                  const isPositive = entry.total_pnl >= 0;

                  return (
                    <tr
                      key={entry.sector}
                      className="border-b border-gray-800/30 last:border-0"
                    >
                      <td className="py-2 pr-4 text-gray-300 font-medium">
                        {entry.sector}
                      </td>
                      <td
                        className={`py-2 px-4 text-right font-medium ${
                          isPositive ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {isPositive ? "+" : ""}
                        {formatCurrency(entry.total_pnl)}
                      </td>
                      <td
                        className={`py-2 px-4 text-right ${
                          isPositive ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {isPositive ? "+" : ""}
                        {entry.total_pnl_pct.toFixed(2)}%
                      </td>
                      <td className="py-2 px-4 text-right text-gray-300">
                        {entry.position_count}
                      </td>
                      <td className="py-2 px-4 text-gray-300 font-mono text-xs">
                        {entry.best_ticker ?? "--"}
                      </td>
                      <td className="py-2 px-4 text-gray-300 font-mono text-xs">
                        {entry.worst_ticker ?? "--"}
                      </td>
                      <td className="py-2 pl-4">
                        <div className="h-3 w-full rounded bg-gray-800 overflow-hidden">
                          <div
                            className={`h-full rounded ${
                              isPositive ? "bg-green-500" : "bg-red-500"
                            }`}
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
