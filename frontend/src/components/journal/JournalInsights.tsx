import { useApi } from "../../hooks/useApi";
import { getJournalInsights } from "../../api/endpoints";
import type { JournalInsight } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";

function SeverityIcon({ severity }: { severity: JournalInsight["severity"] }) {
  if (severity === "positive") {
    return (
      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-emerald-500/10 text-emerald-400 text-lg shrink-0">
        &#x2713;
      </span>
    );
  }
  if (severity === "negative") {
    return (
      <span className="flex items-center justify-center w-8 h-8 rounded-full bg-red-500/10 text-red-400 text-lg shrink-0">
        &#x26A0;
      </span>
    );
  }
  return (
    <span className="flex items-center justify-center w-8 h-8 rounded-full bg-gray-700/50 text-gray-400 text-lg shrink-0">
      &#x2139;
    </span>
  );
}

function formatMetric(value: number | null, type: string): string | null {
  if (value == null) return null;
  if (
    type === "best_sector" ||
    type === "win_rate_trend" ||
    type === "win_rate"
  ) {
    return `${value >= 0 ? "+" : ""}${value}%`;
  }
  if (type === "hold_return_correlation") {
    return `r = ${value}`;
  }
  if (type === "position_sizing") {
    return `${value >= 0 ? "+" : ""}${value}%`;
  }
  if (type === "hold_time") {
    return `${value}d`;
  }
  return String(value);
}

export default function JournalInsights() {
  const { data, loading, error, refetch } = useApi<JournalInsight[]>(
    () => getJournalInsights(),
    { cacheKey: "journal:insights", ttlMs: 60_000 },
  );

  if (loading) return <SkeletonCard />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;
  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader title="Trading Insights" />
        <CardBody>
          <EmptyState message="No insights available yet." />
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Trading Insights"
        subtitle={`${data.length} insight${data.length !== 1 ? "s" : ""}`}
      />
      <CardBody>
        <div className="space-y-3">
          {data.map((insight, idx) => (
            <div
              key={`${insight.type}-${idx}`}
              className="flex items-start gap-3 p-3 rounded-lg bg-gray-800/40 border border-gray-700/30"
            >
              <SeverityIcon severity={insight.severity} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-sm font-semibold text-gray-200">
                    {insight.title}
                  </h4>
                  {insight.metric_value != null && (
                    <span className="text-xs font-mono text-gray-400 shrink-0">
                      {formatMetric(insight.metric_value, insight.type)}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                  {insight.detail}
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
