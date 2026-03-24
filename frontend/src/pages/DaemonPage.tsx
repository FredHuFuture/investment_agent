import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { getDaemonStatus, daemonRunOnce } from "../api/endpoints";
import type { DaemonStatus } from "../api/types";
import { formatDate } from "../lib/formatters";

/** Extended job status including optional fields returned by the backend. */
interface DaemonJobEntry {
  status: string;
  last_run: string | null;
  duration_ms?: number;
  result_json?: string;
  error_message?: string;
}
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import { Button } from "../components/ui/Button";
import { Card, CardHeader, CardBody } from "../components/ui/Card";
import { SkeletonCard } from "../components/ui/Skeleton";
import { useToast } from "../contexts/ToastContext";
import { usePageTitle } from "../hooks/usePageTitle";
import DaemonJobResultPanel from "../components/monitoring/DaemonJobResultPanel";
import DaemonRunHistory from "../components/daemon/DaemonRunHistory";

type TriggerType = "daily" | "weekly" | "regime" | "watchlist" | null;

const JOB_META: Record<
  string,
  { label: string; description: string; trigger: TriggerType }
> = {
  daily_check: {
    label: "Daily Check",
    description: "Monitor positions, check stop-loss/target-hit, generate alerts",
    trigger: "daily",
  },
  weekly_revaluation: {
    label: "Weekly Revaluation",
    description: "Re-run all agents on portfolio positions, update signals",
    trigger: "weekly",
  },
  catalyst_scan: {
    label: "Catalyst Scan",
    description: "Scan news & catalysts for portfolio tickers (requires LLM)",
    trigger: null,
  },
  regime_detection: {
    label: "Regime Detection",
    description:
      "Detect current market regime (bull/bear/sideways/high-vol/risk-off) and save to history",
    trigger: "regime",
  },
  watchlist_scan: {
    label: "Watchlist Scan",
    description:
      "Evaluate watchlist alert configs and generate price/signal alerts",
    trigger: "watchlist",
  },
};

function StatusDot({ status }: { status: string }) {
  const color =
    status === "success"
      ? "bg-green-400"
      : status === "running"
        ? "bg-accent-light animate-pulse"
        : status === "error" || status === "failed"
          ? "bg-red-400"
          : "bg-gray-600";
  return <span className={`w-2.5 h-2.5 rounded-full ${color}`} />;
}

function StatusLabel({ status }: { status: string }) {
  const styles =
    status === "success"
      ? "text-green-400"
      : status === "running"
        ? "text-accent-light"
        : status === "error" || status === "failed"
          ? "text-red-400"
          : "text-gray-500";
  return (
    <span className={`text-xs font-medium capitalize ${styles}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export default function DaemonPage() {
  usePageTitle("Daemon");
  const { toast } = useToast();
  const { data, loading, error, refetch } = useApi<DaemonStatus>(
    () => getDaemonStatus(),
  );
  const [running, setRunning] = useState<string | null>(null);
  const [expandedJob, setExpandedJob] = useState<string | null>(null);
  const [historyJob, setHistoryJob] = useState<string | null>(null);

  async function handleRunOnce(job: "daily" | "weekly" | "regime" | "watchlist") {
    setRunning(job);
    try {
      await daemonRunOnce(job);
      toast.success("Job completed");
      refetch();
    } catch (err) {
      toast.error(
        "Run failed",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setRunning(null);
    }
  }

  if (loading)
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  const jobs = data
    ? Object.entries(data).map(([name, rawJob]) => {
        const job = rawJob as DaemonJobEntry;
        return {
          name,
          status: job.status,
          last_run: job.last_run,
          result_json: job.result_json,
          error_message: job.error_message,
          meta: JOB_META[name] ?? {
            label: name.replace(/_/g, " "),
            description: "",
            trigger: null as TriggerType,
          },
        };
      })
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Daemon</h1>
        <p className="text-sm text-gray-500 mt-1">
          Background jobs for continuous portfolio monitoring
        </p>
      </div>

      {jobs.length === 0 ? (
        <EmptyState message="No daemon jobs configured." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {jobs.map((job) => (
            <Card key={job.name} padding="md" className="flex flex-col">
              {/* Header */}
              <div className="flex items-center gap-2.5 mb-3">
                <StatusDot status={job.status} />
                <h3 className="text-sm font-semibold text-gray-200">
                  {job.meta.label}
                </h3>
              </div>

              {/* Description */}
              <p className="text-xs text-gray-500 mb-4 flex-1">
                {job.meta.description}
              </p>

              {/* Status row */}
              <div className="flex items-center justify-between text-xs mb-4">
                <div>
                  <span className="text-gray-600">Status: </span>
                  <StatusLabel status={job.status} />
                </div>
                <div className="text-gray-500">
                  {job.last_run ? formatDate(job.last_run) : "Never run"}
                </div>
              </div>

              {/* Action button */}
              {job.meta.trigger && (
                <Button
                  variant={job.meta.trigger === "daily" ? "primary" : "secondary"}
                  size="sm"
                  loading={running === job.meta.trigger}
                  disabled={running !== null}
                  onClick={() => handleRunOnce(job.meta.trigger as "daily" | "weekly" | "regime" | "watchlist")}
                  className="w-full"
                >
                  {`Run ${job.meta.label}`}
                </Button>
              )}
              {!job.meta.trigger && (
                <div className="w-full text-center py-2 rounded-lg text-xs text-gray-600 bg-gray-800/30 border border-gray-800/30">
                  Requires LLM (Task 023)
                </div>
              )}

              {/* History toggle */}
              <button
                type="button"
                className="mt-2 w-full text-xs text-gray-400 hover:text-gray-200 transition-colors text-center py-1"
                onClick={() => setHistoryJob(historyJob === job.name ? null : job.name)}
              >
                {historyJob === job.name ? "Close History" : "View History"}
              </button>

              {/* Details toggle */}
              {job.result_json && (
                <button
                  type="button"
                  className="mt-2 text-xs text-accent-light hover:text-accent transition-colors text-left"
                  onClick={() =>
                    setExpandedJob(
                      expandedJob === job.name ? null : job.name,
                    )
                  }
                >
                  {expandedJob === job.name ? "Hide Details" : "Details"}
                </button>
              )}

              {/* Expandable result panel */}
              {expandedJob === job.name && job.result_json && (
                <DaemonJobResultPanel
                  resultJson={job.result_json}
                  errorMessage={job.error_message}
                />
              )}
            </Card>
          ))}
        </div>
      )}

      {historyJob && (
        <Card>
          <CardHeader
            title={`Run History \u2014 ${JOB_META[historyJob]?.label ?? historyJob}`}
            action={<Button variant="ghost" size="sm" onClick={() => setHistoryJob(null)}>Close</Button>}
          />
          <CardBody>
            <DaemonRunHistory jobName={historyJob} />
          </CardBody>
        </Card>
      )}
    </div>
  );
}
