import { useState, useCallback, useMemo } from "react";
import { useApi } from "../hooks/useApi";
import { getAlerts, batchAcknowledgeAlerts } from "../api/endpoints";
import type { Alert } from "../api/types";
import AlertTimeline from "../components/monitoring/AlertTimeline";
import AlertAnalyticsPanel from "../components/monitoring/AlertAnalyticsPanel";
import AlertSummaryChips from "../components/monitoring/AlertSummaryChips";
import SeverityFilterBar from "../components/monitoring/SeverityFilterBar";
import MonitorCheckButton from "../components/monitoring/MonitorCheckButton";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import { SkeletonTable } from "../components/ui/Skeleton";
import { Button } from "../components/ui/Button";
import { useToast } from "../contexts/ToastContext";
import { usePageTitle } from "../hooks/usePageTitle";

type AckFilter = "all" | "0" | "1";

export default function MonitoringPage() {
  usePageTitle("Monitoring");
  const { toast } = useToast();
  const [ackFilter, setAckFilter] = useState<AckFilter>("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);

  const fetcher = useCallback(() => {
    const params: { limit: number; acknowledged?: number; severity?: string } = {
      limit: 50,
    };
    if (ackFilter !== "all") {
      params.acknowledged = Number(ackFilter);
    }
    if (severityFilter !== "all") {
      params.severity = severityFilter;
    }
    return getAlerts(params);
  }, [ackFilter, severityFilter]);

  const { data, loading, error, refetch } = useApi<Alert[]>(
    fetcher,
    [ackFilter, severityFilter],
    { cacheKey: `monitoring:alerts:${ackFilter}:${severityFilter}`, ttlMs: 15_000 },
  );

  // Compute severity counts from raw (unfiltered) data for the filter bar
  // We fetch unfiltered alerts separately for counts, or compute from current data
  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    if (data) {
      for (const alert of data) {
        const sev = alert.severity.toUpperCase();
        counts[sev] = (counts[sev] || 0) + 1;
      }
    }
    return counts;
  }, [data]);

  // Toggle a single alert selection
  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  // Select/deselect all unacknowledged alerts
  function toggleSelectAll() {
    if (!data) return;
    const unacked = data.filter((a) => a.acknowledged === 0);
    const allSelected = unacked.length > 0 && unacked.every((a) => selectedIds.has(a.id));
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(unacked.map((a) => a.id)));
    }
  }

  async function handleBatchAcknowledge() {
    if (selectedIds.size === 0) return;
    setBatchLoading(true);
    try {
      const ids = Array.from(selectedIds);
      await batchAcknowledgeAlerts(ids);
      toast.success(`Acknowledged ${ids.length} alert${ids.length > 1 ? "s" : ""}`);
      setSelectedIds(new Set());
      refetch();
    } catch (err) {
      toast.error(
        "Batch acknowledge failed",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setBatchLoading(false);
    }
  }

  function handleSeverityChange(severity: string) {
    setSeverityFilter(severity);
    setSelectedIds(new Set());
  }

  function handleRefetch() {
    setSelectedIds(new Set());
    refetch();
  }

  if (loading) return <SkeletonTable rows={5} columns={4} />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  const unackedCount = data ? data.filter((a) => a.acknowledged === 0).length : 0;
  const allUnackedSelected =
    unackedCount > 0 &&
    data!.filter((a) => a.acknowledged === 0).every((a) => selectedIds.has(a.id));

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-white">Monitoring</h1>
        <MonitorCheckButton onComplete={handleRefetch} />
      </div>

      {/* Alert timeline chart */}
      <AlertTimeline />

      {/* Alert analytics panel */}
      <AlertAnalyticsPanel />

      {/* Summary chips */}
      {data && data.length > 0 && <AlertSummaryChips alerts={data} />}

      {/* Severity filter bar */}
      <SeverityFilterBar
        selectedSeverity={severityFilter}
        onChange={handleSeverityChange}
        counts={severityCounts}
      />

      {/* Ack filter + batch actions */}
      <div className="flex items-center justify-between gap-4">
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
        </div>
        {selectedIds.size > 0 && (
          <Button
            variant="primary"
            size="sm"
            loading={batchLoading}
            onClick={handleBatchAcknowledge}
          >
            Acknowledge Selected ({selectedIds.size})
          </Button>
        )}
      </div>

      {/* Alerts table */}
      {!data || data.length === 0 ? (
        <EmptyState message="No alerts. Run a health check to generate alerts." />
      ) : (
        <div className="overflow-x-auto rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50">
          <table className="w-full text-sm table-auto">
            <thead>
              <tr className="border-b border-gray-800/50 bg-gray-900/30">
                <th className="px-3 py-2.5 text-left">
                  <input
                    type="checkbox"
                    checked={allUnackedSelected}
                    onChange={toggleSelectAll}
                    className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                    title="Select all unacknowledged"
                  />
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                  Severity
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                  Ticker
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold hidden md:table-cell">
                  Type
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                  Message
                </th>
                <th className="px-3 py-2.5 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold hidden md:table-cell">
                  Time
                </th>
                <th className="px-3 py-2.5 text-right text-[11px] uppercase tracking-wider text-gray-500 font-semibold hidden md:table-cell">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((alert) => (
                <AlertRow
                  key={alert.id}
                  alert={alert}
                  selected={selectedIds.has(alert.id)}
                  onToggle={() => toggleSelect(alert.id)}
                  onMutate={handleRefetch}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alert row with checkbox
// ---------------------------------------------------------------------------

import { severityBg } from "../lib/colors";
import { formatDate } from "../lib/formatters";
import { acknowledgeAlert, deleteAlert } from "../api/endpoints";
import ConfirmModal from "../components/ui/ConfirmModal";

function formatAlertType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

interface AlertRowProps {
  alert: Alert;
  selected: boolean;
  onToggle: () => void;
  onMutate: () => void;
}

function AlertRow({ alert, selected, onToggle, onMutate }: AlertRowProps) {
  const { toast } = useToast();
  const [ackLoading, setAckLoading] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Alert | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  async function handleAcknowledge() {
    setAckLoading(true);
    try {
      await acknowledgeAlert(alert.id);
      toast.success("Alert acknowledged");
      onMutate();
    } catch (err) {
      toast.error(
        "Failed to acknowledge alert",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setAckLoading(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      await deleteAlert(deleteTarget.id);
      toast.success("Alert deleted");
      setDeleteTarget(null);
      onMutate();
    } catch (err) {
      toast.error(
        "Failed to delete alert",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setDeleteLoading(false);
    }
  }

  return (
    <>
      <tr className="border-b border-gray-800/30 hover:bg-gray-800/40 transition-colors">
        <td className="px-3 py-2.5">
          {alert.acknowledged === 0 ? (
            <input
              type="checkbox"
              checked={selected}
              onChange={onToggle}
              className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
            />
          ) : (
            <span className="text-green-400 text-sm font-semibold">&#10003;</span>
          )}
        </td>
        <td className="px-3 py-2.5 whitespace-nowrap">
          <span
            className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
              severityBg[alert.severity] ?? "bg-gray-700 text-gray-300"
            }`}
          >
            {alert.severity}
          </span>
        </td>
        <td className="px-3 py-2.5 whitespace-nowrap">
          <span className="font-mono">{alert.ticker ?? "PORTFOLIO"}</span>
        </td>
        <td className="px-3 py-2.5 whitespace-nowrap hidden md:table-cell">
          <span className="text-gray-300 text-xs">
            {formatAlertType(alert.alert_type)}
          </span>
        </td>
        <td className="px-3 py-2.5">
          <span className="text-gray-300 text-xs break-words whitespace-normal max-w-xs inline-block">
            {alert.message}
          </span>
        </td>
        <td className="px-3 py-2.5 whitespace-nowrap hidden md:table-cell">
          <span className="text-gray-500 text-xs">{formatDate(alert.created_at)}</span>
        </td>
        <td className="px-3 py-2.5 whitespace-nowrap hidden md:table-cell">
          <div className="flex items-center justify-end gap-2">
            {alert.acknowledged === 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleAcknowledge}
                loading={ackLoading}
                title="Acknowledge"
              >
                Ack
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="text-red-400 hover:text-red-300 hover:bg-red-900/30"
              onClick={() => setDeleteTarget(alert)}
              title="Delete"
            >
              &times;
            </Button>
          </div>
        </td>
      </tr>
      <ConfirmModal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete Alert"
        description={
          deleteTarget
            ? `Delete the ${deleteTarget.severity} alert for ${deleteTarget.ticker ?? "PORTFOLIO"}?`
            : undefined
        }
        confirmLabel="Delete"
        variant="danger"
        loading={deleteLoading}
      />
    </>
  );
}
