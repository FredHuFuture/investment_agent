import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { getDaemonHistory } from "../../api/endpoints";
import type { DaemonRunEntry } from "../../api/types";
import { formatDate } from "../../lib/formatters";
import { Skeleton } from "../ui/Skeleton";
import DaemonJobResultPanel from "../monitoring/DaemonJobResultPanel";

interface DaemonRunHistoryProps {
  jobName: string;
}

/** Format duration_ms into a human-readable string like "1.2s" or "450ms". */
function formatDuration(ms: number | null): string {
  if (ms == null) return "\u2014";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Colored status badge matching DaemonPage conventions. */
function StatusBadge({ status }: { status: string }) {
  const styles =
    status === "success"
      ? "bg-green-400/10 text-green-400 border-green-400/20"
      : status === "running"
        ? "bg-accent-light/10 text-accent-light border-accent-light/20"
        : status === "error" || status === "failed"
          ? "bg-red-400/10 text-red-400 border-red-400/20"
          : "bg-gray-600/10 text-gray-500 border-gray-600/20";

  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium border capitalize ${styles}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

/** Mini status dots showing last N runs at a glance. */
function StatusDotsRow({ runs }: { runs: DaemonRunEntry[] }) {
  const recent = runs.slice(0, 10);
  return (
    <div className="flex items-center gap-1.5 mb-4">
      <span className="text-[11px] text-gray-600 mr-1">Recent:</span>
      {recent.map((run) => {
        const color =
          run.status === "success"
            ? "bg-green-400"
            : run.status === "error" || run.status === "failed"
              ? "bg-red-400"
              : "bg-gray-600";
        return (
          <span
            key={run.id}
            className={`w-2 h-2 rounded-full ${color}`}
            title={`${run.status} — ${run.started_at}`}
          />
        );
      })}
      {recent.length === 0 && (
        <span className="text-[11px] text-gray-600 italic">none</span>
      )}
    </div>
  );
}

export default function DaemonRunHistory({ jobName }: DaemonRunHistoryProps) {
  const { data, loading, error } = useApi<DaemonRunEntry[]>(
    () => getDaemonHistory(jobName),
    [jobName],
  );
  const [expandedId, setExpandedId] = useState<number | null>(null);

  /* Loading state */
  if (loading) {
    return (
      <div className="space-y-2">
        <Skeleton variant="text" width="30%" />
        <Skeleton variant="rectangular" height={120} />
      </div>
    );
  }

  /* Error state */
  if (error) {
    return (
      <p className="text-sm text-red-400">
        Failed to load history: {error}
      </p>
    );
  }

  const runs = data ?? [];

  /* Empty state */
  if (runs.length === 0) {
    return (
      <p className="text-sm text-gray-500 py-4 text-center">No run history</p>
    );
  }

  return (
    <div>
      <StatusDotsRow runs={runs} />

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800/50">
              <th className="text-left text-xs font-medium text-gray-500 pb-2 pr-4">
                Started
              </th>
              <th className="text-left text-xs font-medium text-gray-500 pb-2 pr-4">
                Status
              </th>
              <th className="text-right text-xs font-medium text-gray-500 pb-2 pr-4">
                Duration
              </th>
              <th className="text-right text-xs font-medium text-gray-500 pb-2">
                Details
              </th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                key={run.id}
                className="border-b border-gray-800/30 last:border-b-0"
              >
                <td className="py-2 pr-4 text-xs text-gray-400 whitespace-nowrap">
                  {formatDate(run.started_at)}
                </td>
                <td className="py-2 pr-4">
                  <StatusBadge status={run.status} />
                </td>
                <td className="py-2 pr-4 text-xs text-gray-400 text-right tabular-nums">
                  {formatDuration(run.duration_ms)}
                </td>
                <td className="py-2 text-right">
                  {(run.result_json || run.error_message) ? (
                    <button
                      type="button"
                      className="text-xs text-accent-light hover:text-accent transition-colors"
                      onClick={() =>
                        setExpandedId(expandedId === run.id ? null : run.id)
                      }
                    >
                      {expandedId === run.id ? "Hide" : "Expand"}
                    </button>
                  ) : (
                    <span className="text-xs text-gray-600">&mdash;</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Expanded result panel — rendered below the table for the selected run */}
      {expandedId != null && (() => {
        const run = runs.find((r) => r.id === expandedId);
        if (!run) return null;
        return (
          <DaemonJobResultPanel
            resultJson={run.result_json ?? "{}"}
            errorMessage={run.error_message}
          />
        );
      })()}
    </div>
  );
}
