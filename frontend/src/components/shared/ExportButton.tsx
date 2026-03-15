import { useState, useCallback, type FC } from "react";
import { Button } from "../ui/Button";
import { useToast } from "../../contexts/ToastContext";

interface ExportButtonProps {
  /** API path like "/api/export/portfolio/csv" */
  endpoint: string;
  /** Download filename like "portfolio.csv" */
  filename: string;
  /** Button text, defaults to "Export" */
  label?: string;
  variant?: "primary" | "ghost" | "secondary";
  size?: "sm" | "md";
}

/** Small arrow-down download icon. */
const DownloadIcon: FC = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </svg>
);

/**
 * Reusable download/export button.
 *
 * On click it fetches the given API endpoint, converts the response to a Blob,
 * creates a temporary anchor element and triggers a browser download.
 */
const ExportButton: FC<ExportButtonProps> = ({
  endpoint,
  filename,
  label = "Export",
  variant = "secondary",
  size = "sm",
}) => {
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handleClick = useCallback(async () => {
    setLoading(true);
    try {
      // The API client uses "/api" as its base prefix (see client.ts).
      // Export endpoints already include that prefix in the `endpoint` prop,
      // so we fetch relative to the current origin.
      const res = await fetch(endpoint);
      if (!res.ok) {
        throw new Error(`Export failed (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      // Clean up
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Export failed";
      toast.error("Export error", message);
    } finally {
      setLoading(false);
    }
  }, [endpoint, filename, toast]);

  return (
    <Button
      variant={variant}
      size={size}
      loading={loading}
      onClick={handleClick}
      aria-label={`${label} ${filename}`}
    >
      {!loading && <DownloadIcon />}
      {label}
    </Button>
  );
};

export default ExportButton;
