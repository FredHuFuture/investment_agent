import { useApi } from "../../hooks/useApi";
import { getSignalHistory } from "../../api/endpoints";
import type { SignalHistoryEntry } from "../../api/types";
import SignalBadge from "../shared/SignalBadge";
import { SkeletonTable } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";

function formatTimelineDate(iso: string): string {
  const d = new Date(iso.replace(" ", "T"));
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatTimelineTime(iso: string): string {
  const d = new Date(iso.replace(" ", "T"));
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen - 3) + "...";
}

const DOT_COLORS: Record<string, string> = {
  BUY: "bg-green-400 shadow-green-400/30",
  SELL: "bg-red-400 shadow-red-400/30",
  HOLD: "bg-gray-400 shadow-gray-400/30",
};

interface Props {
  ticker: string | null;
}

export default function SignalTimeline({ ticker }: Props) {
  const { data, loading, error, refetch } = useApi<SignalHistoryEntry[]>(
    () => getSignalHistory({ ticker: ticker || undefined, limit: 20 }),
    [ticker],
    {
      cacheKey: ticker ? `signals:timeline:${ticker}` : undefined,
      ttlMs: 30_000,
    },
  );

  if (!ticker) {
    return (
      <EmptyState
        message="Select a ticker to see signal timeline"
        hint="Enter a ticker symbol above to view recent signals."
      />
    );
  }

  if (loading) return <SkeletonTable rows={6} columns={3} />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;
  if (!data || data.length === 0) {
    return <EmptyState message={`No signals found for ${ticker}.`} />;
  }

  return (
    <div className="relative pl-6">
      {/* Vertical timeline line */}
      <div className="absolute left-[11px] top-2 bottom-2 w-px bg-gray-800" />

      {data.map((entry, idx) => {
        const dotColor = DOT_COLORS[entry.final_signal] ?? DOT_COLORS.HOLD;
        const isLast = idx === data.length - 1;

        return (
          <div
            key={entry.id}
            className={`relative flex items-start gap-4 ${isLast ? "" : "pb-5"}`}
          >
            {/* Timeline dot */}
            <div
              className={`absolute left-[-17px] top-1.5 w-2.5 h-2.5 rounded-full shadow-sm ${dotColor}`}
            />

            {/* Date column */}
            <div className="flex-shrink-0 w-24 text-right">
              <div className="text-xs text-gray-400 font-mono">
                {formatTimelineDate(entry.created_at)}
              </div>
              <div className="text-[10px] text-gray-600 font-mono">
                {formatTimelineTime(entry.created_at)}
              </div>
            </div>

            {/* Signal + confidence */}
            <div className="flex-shrink-0 flex items-center gap-2">
              <SignalBadge signal={entry.final_signal} />
              <span className="text-xs font-mono text-gray-400">
                {entry.final_confidence.toFixed(0)}%
              </span>
            </div>

            {/* Reasoning */}
            <div className="flex-1 min-w-0">
              <p className="text-xs text-gray-500 leading-relaxed">
                {truncate(entry.reasoning || "", 80)}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
