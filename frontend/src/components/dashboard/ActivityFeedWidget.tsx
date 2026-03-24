import { useApi } from "../../hooks/useApi";
import { getActivityFeed } from "../../api/endpoints";
import type { ActivityFeedEntry } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import EmptyState from "../shared/EmptyState";

/** Convert a date string to a relative "time ago" label. */
function timeAgo(dateString: string): string {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  const diffMs = now - then;

  if (diffMs < 0) return "just now";

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;

  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

/** Colored left-border class based on severity. */
const severityBorderMap: Record<string, string> = {
  critical: "border-l-red-500",
  high: "border-l-orange-500",
  warning: "border-l-yellow-500",
  info: "border-l-accent",
};

/** Dot color based on entry type. */
const typeDotMap: Record<string, string> = {
  daemon_run: "bg-gray-400",
  alert: "bg-red-400",
  signal: "bg-accent-light",
  trade: "bg-green-400",
};

export default function ActivityFeedWidget() {
  const { data, loading, error } = useApi<ActivityFeedEntry[]>(
    () => getActivityFeed(10),
    { cacheKey: "dashboard:activityFeed", ttlMs: 60_000 },
  );

  if (loading) return <SkeletonCard />;

  if (error || !data) {
    return (
      <Card>
        <CardHeader title="Recent Activity" />
        <CardBody>
          <p className="text-sm text-gray-500">Unable to load activity feed.</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Recent Activity" />
      <CardBody>
        {data.length === 0 ? (
          <EmptyState message="No recent activity." />
        ) : (
          <ul className="space-y-2">
            {data.slice(0, 10).map((entry, idx) => {
              const borderClass =
                severityBorderMap[entry.severity ?? "info"] ??
                "border-l-gray-600";
              const dotClass =
                typeDotMap[entry.type] ?? "bg-gray-500";

              return (
                <li
                  key={`${entry.type}-${entry.timestamp}-${idx}`}
                  className={`border-l-2 ${borderClass} pl-3 py-1.5`}
                >
                  <div className="flex items-start gap-2">
                    <span
                      className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${dotClass}`}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-sm font-medium text-gray-200 truncate">
                          {entry.title}
                        </span>
                        <span className="text-xs text-gray-500 shrink-0">
                          {entry.timestamp ? timeAgo(entry.timestamp) : "--"}
                        </span>
                      </div>
                      {entry.detail && (
                        <p className="text-xs text-gray-400 mt-0.5 truncate">
                          {entry.detail}
                        </p>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
