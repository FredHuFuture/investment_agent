import { useState, useCallback } from "react";
import { useApi } from "../hooks/useApi";
import { getAlerts } from "../api/endpoints";
import type { Alert } from "../api/types";
import AlertsList from "../components/monitoring/AlertsList";
import MonitorCheckButton from "../components/monitoring/MonitorCheckButton";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import { SkeletonTable } from "../components/ui/Skeleton";
import { usePageTitle } from "../hooks/usePageTitle";

type AckFilter = "all" | "0" | "1";

export default function MonitoringPage() {
  usePageTitle("Monitoring");
  const [ackFilter, setAckFilter] = useState<AckFilter>("all");

  const fetcher = useCallback(() => {
    const params: { limit: number; acknowledged?: number } = { limit: 50 };
    if (ackFilter !== "all") {
      params.acknowledged = Number(ackFilter);
    }
    return getAlerts(params);
  }, [ackFilter]);

  const { data, loading, error, refetch } = useApi<Alert[]>(
    fetcher,
    [ackFilter],
    { cacheKey: `monitoring:alerts:${ackFilter}`, ttlMs: 15_000 },
  );

  if (loading) return <SkeletonTable rows={5} columns={4} />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-white">Monitoring</h1>
        <div className="flex items-center gap-3">
          <select
            value={ackFilter}
            onChange={(e) => setAckFilter(e.target.value as AckFilter)}
            className="rounded-lg bg-gray-800 border border-gray-700 text-gray-200 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All</option>
            <option value="0">Unacknowledged</option>
            <option value="1">Acknowledged</option>
          </select>
          <MonitorCheckButton onComplete={refetch} />
        </div>
      </div>
      {!data || data.length === 0 ? (
        <EmptyState message="No alerts. Run a health check to generate alerts." />
      ) : (
        <AlertsList alerts={data} onMutate={refetch} />
      )}
    </div>
  );
}
