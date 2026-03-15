import { useApi } from "../../hooks/useApi";
import { getSystemInfo } from "../../api/endpoints";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";

const STAT_ROWS: { label: string; key: "total_positions" | "total_closed" | "total_signals" | "total_alerts" }[] = [
  { label: "Open Positions", key: "total_positions" },
  { label: "Closed Positions", key: "total_closed" },
  { label: "Total Signals", key: "total_signals" },
  { label: "Total Alerts", key: "total_alerts" },
];

function truncatePath(path: string, maxLen = 45): string {
  if (path.length <= maxLen) return path;
  return "..." + path.slice(path.length - maxLen + 3);
}

export default function SystemInfoCard() {
  const { data, loading, error } = useApi(getSystemInfo, {
    cacheKey: "system_info",
    ttlMs: 60_000,
  });

  if (loading && !data) {
    return <SkeletonCard />;
  }

  return (
    <Card>
      <CardHeader title="System Info" subtitle="Database and runtime status" />
      <CardBody>
        {error && !data && (
          <p className="text-xs text-red-400">{error}</p>
        )}

        {data && (
          <div className="space-y-4">
            {/* Status + Version row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    data.status === "ok" ? "bg-green-500" : "bg-red-500"
                  }`}
                />
                <span className="text-xs font-medium text-gray-200">
                  {data.status === "ok" ? "Healthy" : "Error"}
                </span>
              </div>
              <span className="text-xs text-gray-500">v{data.version}</span>
            </div>

            {/* DB path */}
            <div>
              <p className="text-[10px] text-gray-500 mb-0.5">Database</p>
              <p className="text-xs text-gray-400 font-mono truncate" title={data.db_path}>
                {truncatePath(data.db_path)}
              </p>
            </div>

            {/* Stats rows */}
            <div className="border-t border-gray-800/50 pt-3 space-y-2">
              {STAT_ROWS.map((row) => (
                <div key={row.key} className="flex items-center justify-between">
                  <span className="text-xs text-gray-400">{row.label}</span>
                  <span className="text-xs font-medium text-gray-200 tabular-nums">
                    {data[row.key].toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
