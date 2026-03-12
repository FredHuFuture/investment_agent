import { useApi } from "../hooks/useApi";
import { getAlerts } from "../api/endpoints";
import type { Alert } from "../api/types";
import AlertsList from "../components/monitoring/AlertsList";
import MonitorCheckButton from "../components/monitoring/MonitorCheckButton";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";

export default function MonitoringPage() {
  const { data, loading, error, refetch } = useApi<Alert[]>(
    () => getAlerts({ limit: 50 }),
  );

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorAlert message={error} />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Monitoring</h1>
        <MonitorCheckButton onComplete={refetch} />
      </div>
      {!data || data.length === 0 ? (
        <EmptyState message="No alerts. Run a health check to generate alerts." />
      ) : (
        <AlertsList alerts={data} />
      )}
    </div>
  );
}
