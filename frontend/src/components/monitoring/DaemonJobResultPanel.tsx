interface DaemonJobResultPanelProps {
  resultJson: string;
  errorMessage?: string | null;
}

interface ParsedResult {
  [key: string]: unknown;
}

/** Humanise a snake_case key into Title Case. */
function humaniseKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Render a single value as a readable string. */
function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    // Percentages or small decimals get formatted
    if (Number.isInteger(value)) return String(value);
    return value.toFixed(2);
  }
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

/** Pick display keys per job type, falling back to all keys. */
function getDisplayEntries(parsed: ParsedResult): Array<[string, unknown]> {
  const all = Object.entries(parsed);

  // regime_detection results
  if ("regime" in parsed) {
    const keys = ["regime", "confidence", "vix", "vix_sma", "trend_score"];
    return keys
      .filter((k) => k in parsed)
      .map((k) => [k, parsed[k]]);
  }

  // watchlist_scan results
  if ("tickers_scanned" in parsed || "alerts_created" in parsed) {
    const keys = ["tickers_scanned", "alerts_created", "errors"];
    return keys
      .filter((k) => k in parsed)
      .map((k) => [k, parsed[k]]);
  }

  // daily_check results
  if ("checked_positions" in parsed || "alerts_generated" in parsed) {
    const keys = ["checked_positions", "alerts_generated", "warnings"];
    return keys
      .filter((k) => k in parsed)
      .map((k) => [k, parsed[k]]);
  }

  // weekly_revaluation results
  if ("positions_analyzed" in parsed || "signal_reversals" in parsed) {
    const keys = ["positions_analyzed", "signal_reversals", "alerts_generated"];
    return keys
      .filter((k) => k in parsed)
      .map((k) => [k, parsed[k]]);
  }

  // Generic fallback — show everything
  return all;
}

export default function DaemonJobResultPanel({
  resultJson,
  errorMessage,
}: DaemonJobResultPanelProps) {
  let parsed: ParsedResult | null = null;
  let parseError = false;

  try {
    parsed = JSON.parse(resultJson) as ParsedResult;
  } catch {
    parseError = true;
  }

  const entries = parsed ? getDisplayEntries(parsed) : [];

  return (
    <div className="mt-3 rounded-lg bg-gray-800/40 border border-gray-700/50 p-3 space-y-2">
      {errorMessage && (
        <p className="text-xs text-red-400 font-medium">{errorMessage}</p>
      )}

      {parseError && (
        <p className="text-xs text-gray-500 italic">
          Unable to parse result data.
        </p>
      )}

      {entries.length > 0 && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          {entries.map(([key, value]) => (
            <div key={key} className="contents">
              <span className="text-xs text-gray-500">{humaniseKey(key)}</span>
              <span className="text-xs text-gray-300 font-medium text-right">
                {renderValue(value)}
              </span>
            </div>
          ))}
        </div>
      )}

      {!parseError && entries.length === 0 && !errorMessage && (
        <p className="text-xs text-gray-500 italic">No result data.</p>
      )}
    </div>
  );
}
