export function formatCurrency(v: number): string {
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

export function formatPct(v: number, decimals = 1): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(decimals)}%`;
}

export function formatDate(iso: string): string {
  // Backend may return "YYYY-MM-DD HH:MM:SS" (space separator); fix for Date parsing
  const d = new Date(iso.replace(" ", "T"));
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatNumber(v: number, decimals = 2): string {
  return v.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Relative time from a timestamp in ms (e.g., Date.now()). Used for "Updated Xm ago" display. */
export function formatRelativeTime(timestamp: number | null): string {
  if (!timestamp) return "";
  const diff = Math.floor((Date.now() - timestamp) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

/** Relative time from an ISO date string. Used for "added 3d ago" display. */
export function formatRelativeDate(dateStr: string): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Color class for P&L values: green positive, red negative, gray zero. */
export function pnlColor(v: number): string {
  if (v > 0) return "text-emerald-400";
  if (v < 0) return "text-red-400";
  return "text-gray-400";
}

/** Color class for hold days vs expected: green (on track), yellow (nearing), red (overdue). */
export function holdColor(held: number, expected: number | null): string {
  if (expected == null) return "text-gray-400";
  const ratio = held / expected;
  if (ratio > 1.0) return "text-red-400";
  if (ratio >= 0.8) return "text-yellow-400";
  return "text-emerald-400";
}
