import { useApi } from "../../hooks/useApi";
import { getPositionTimeline } from "../../api/endpoints";
import type { PositionEvent } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import EmptyState from "../shared/EmptyState";
import { formatDate } from "../../lib/formatters";

// ---------------------------------------------------------------------------
// Dot color mapping
// ---------------------------------------------------------------------------
function dotColor(event: PositionEvent): string {
  switch (event.type) {
    case "entry":
      return "bg-emerald-400";
    case "signal":
      return "bg-blue-400";
    case "alert": {
      const sev = (event.severity ?? "").toLowerCase();
      if (sev === "critical" || sev === "high") return "bg-red-400";
      if (sev === "warning") return "bg-orange-400";
      return "bg-yellow-400";
    }
    case "thesis_change":
      return "bg-purple-400";
    case "annotation":
      return "bg-gray-400";
    case "exit":
      return "bg-red-400";
    default:
      return "bg-gray-400";
  }
}

function lineColor(event: PositionEvent): string {
  switch (event.type) {
    case "entry":
      return "border-emerald-400/30";
    case "signal":
      return "border-blue-400/30";
    case "alert":
      return "border-red-400/30";
    case "thesis_change":
      return "border-purple-400/30";
    case "annotation":
      return "border-gray-400/30";
    case "exit":
      return "border-red-400/30";
    default:
      return "border-gray-400/30";
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
interface PositionTimelineProps {
  ticker: string;
}

export default function PositionTimeline({ ticker }: PositionTimelineProps) {
  const api = useApi<PositionEvent[]>(
    () => getPositionTimeline(ticker),
    [ticker],
  );

  return (
    <Card>
      <CardHeader title="Position Timeline" />
      <CardBody>
        {api.loading && (
          <div className="space-y-4">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="flex gap-3">
                <Skeleton variant="rectangular" width={12} height={12} />
                <div className="flex-1 space-y-1">
                  <Skeleton variant="text" width="40%" height={14} />
                  <Skeleton variant="text" width="70%" height={12} />
                </div>
              </div>
            ))}
          </div>
        )}

        {api.error && (
          <p className="text-gray-500 text-sm">
            Could not load timeline data.
          </p>
        )}

        {api.data && api.data.length === 0 && !api.loading && (
          <EmptyState message="No timeline events found for this position." />
        )}

        {api.data && api.data.length > 0 && (
          <div className="relative">
            {api.data.map((event, idx) => (
              <div key={`${event.type}-${event.date}-${idx}`} className="flex gap-3">
                {/* Vertical line + dot */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${dotColor(event)}`}
                  />
                  {idx < api.data!.length - 1 && (
                    <div
                      className={`w-px flex-1 border-l-2 ${lineColor(event)}`}
                    />
                  )}
                </div>

                {/* Content */}
                <div className="pb-5 min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] text-gray-600 font-mono">
                      {formatDate(event.date)}
                    </span>
                    <span className="text-[10px] uppercase tracking-wider text-gray-600 bg-gray-800/40 px-1.5 py-0.5 rounded">
                      {event.type.replace("_", " ")}
                    </span>
                  </div>
                  <p className="text-sm text-gray-200 mt-0.5 leading-snug">
                    {event.title}
                  </p>
                  {event.detail && (
                    <p className="text-xs text-gray-500 mt-0.5 leading-relaxed line-clamp-2">
                      {event.detail}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
