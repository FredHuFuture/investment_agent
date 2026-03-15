import { useState } from "react";
import DataTable, { type Column } from "../shared/DataTable";
import { severityBg } from "../../lib/colors";
import { formatDate } from "../../lib/formatters";
import type { Alert } from "../../api/types";
import { acknowledgeAlert, deleteAlert } from "../../api/endpoints";
import { useToast } from "../../contexts/ToastContext";
import ConfirmModal from "../ui/ConfirmModal";
import { Button } from "../ui/Button";

/** TARGET_HIT → "Target Hit", SIGNIFICANT_GAIN → "Significant Gain" */
function formatAlertType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

interface AlertsListProps {
  alerts: Alert[];
  onMutate: () => void;
}

export default function AlertsList({ alerts, onMutate }: AlertsListProps) {
  const { toast } = useToast();
  const [ackLoading, setAckLoading] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Alert | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  async function handleAcknowledge(alert: Alert) {
    setAckLoading(alert.id);
    try {
      await acknowledgeAlert(alert.id);
      toast.success("Alert acknowledged");
      onMutate();
    } catch (err) {
      toast.error("Failed to acknowledge alert", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setAckLoading(null);
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
      toast.error("Failed to delete alert", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setDeleteLoading(false);
    }
  }

  const columns: Column<Alert>[] = [
    {
      key: "severity",
      header: "Severity",
      render: (r) => (
        <span
          className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
            severityBg[r.severity] ?? "bg-gray-700 text-gray-300"
          }`}
        >
          {r.severity}
        </span>
      ),
    },
    {
      key: "ticker",
      header: "Ticker",
      render: (r) => (
        <span className="font-mono">{r.ticker ?? "PORTFOLIO"}</span>
      ),
      sortValue: (r) => r.ticker ?? "",
    },
    {
      key: "type",
      header: "Type",
      render: (r) => <span className="text-gray-300 text-xs">{formatAlertType(r.alert_type)}</span>,
    },
    {
      key: "message",
      header: "Message",
      render: (r) => (
        <span className="text-gray-300 text-xs break-words whitespace-normal max-w-xs inline-block">
          {r.message}
        </span>
      ),
    },
    {
      key: "time",
      header: "Time",
      render: (r) => (
        <span className="text-gray-500 text-xs">{formatDate(r.created_at)}</span>
      ),
      sortValue: (r) => r.created_at,
    },
    {
      key: "actions",
      header: "Actions",
      hiddenOnMobile: true,
      render: (r) => (
        <div className="flex items-center justify-end gap-2">
          {r.acknowledged === 1 ? (
            <span className="text-green-400 text-sm font-semibold px-2">&#10003;</span>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                handleAcknowledge(r);
              }}
              loading={ackLoading === r.id}
              title="Acknowledge"
            >
              Ack
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="text-red-400 hover:text-red-300 hover:bg-red-900/30"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteTarget(r);
            }}
            title="Delete"
          >
            &times;
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <DataTable columns={columns} data={alerts} keyFn={(r) => r.id} />
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
