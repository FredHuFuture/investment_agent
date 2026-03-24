import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { getAnalysisHistory, getAnalyzedTickers } from "../api/endpoints";
import type { AnalysisHistoryEntry } from "../api/types";
import { Card, CardBody } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SkeletonTable } from "../components/ui/Skeleton";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import { formatDate } from "../lib/formatters";
import { usePageTitle } from "../hooks/usePageTitle";

const SIGNAL_OPTIONS = ["", "BUY", "HOLD", "SELL"] as const;

function signalBadge(signal: string) {
  const colors: Record<string, string> = {
    BUY: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    SELL: "bg-red-500/20 text-red-400 border-red-500/30",
    HOLD: "bg-gray-500/20 text-gray-400 border-gray-500/30",
  };
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-semibold border ${
        colors[signal] ?? "bg-gray-500/20 text-gray-400 border-gray-500/30"
      }`}
    >
      {signal}
    </span>
  );
}

function regimeBadge(regime: string | null) {
  if (!regime) return null;
  return (
    <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-accent/15 text-accent-light border border-accent/30">
      {regime}
    </span>
  );
}

export default function AnalysisHistoryPage() {
  usePageTitle("Analysis History");

  const [tickerFilter, setTickerFilter] = useState("");
  const [signalFilter, setSignalFilter] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Fetch distinct tickers for the dropdown
  const tickers = useApi<string[]>(
    () => getAnalyzedTickers(),
    [],
    { cacheKey: "analysis-history:tickers", ttlMs: 60_000 },
  );

  // Fetch analysis history entries
  const history = useApi<AnalysisHistoryEntry[]>(
    () =>
      getAnalysisHistory({
        ticker: tickerFilter || undefined,
        signal: signalFilter || undefined,
        limit: 20,
      }),
    [tickerFilter, signalFilter],
    { cacheKey: `analysis-history:${tickerFilter}:${signalFilter}`, ttlMs: 30_000 },
  );

  const toggleExpanded = useCallback(
    (id: number) => setExpandedId((prev) => (prev === id ? null : id)),
    [],
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Analysis History</h1>
        <p className="text-sm text-gray-400 mt-1">Browse past analysis results</p>
      </div>

      {/* Filters row */}
      <div className="flex flex-wrap items-end gap-3">
        {/* Ticker dropdown */}
        <div className="flex flex-col">
          <label
            htmlFor="ticker-filter"
            className="text-sm font-medium text-gray-300 mb-1.5"
          >
            Ticker
          </label>
          <select
            id="ticker-filter"
            value={tickerFilter}
            onChange={(e) => setTickerFilter(e.target.value)}
            className="w-36 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-100 focus:ring-2 focus:ring-accent focus:border-accent outline-none transition-colors duration-150"
          >
            <option value="">All Tickers</option>
            {(tickers.data ?? []).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        {/* Signal filter buttons */}
        <div className="flex flex-col">
          <span className="text-sm font-medium text-gray-300 mb-1.5">Signal</span>
          <div className="flex gap-1">
            {SIGNAL_OPTIONS.map((s) => (
              <Button
                key={s || "__all__"}
                variant={signalFilter === s ? "primary" : "ghost"}
                size="sm"
                onClick={() => setSignalFilter(s)}
              >
                {s || "All"}
              </Button>
            ))}
          </div>
        </div>

        {/* Clear button */}
        {(tickerFilter || signalFilter) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setTickerFilter("");
              setSignalFilter("");
            }}
          >
            Clear
          </Button>
        )}
      </div>

      {/* Results */}
      {history.loading ? (
        <SkeletonTable rows={6} columns={5} />
      ) : history.error ? (
        <ErrorAlert message={history.error} onRetry={history.refetch} />
      ) : !history.data?.length ? (
        <EmptyState message="No analysis history found. Run an analysis first." />
      ) : (
        <div className="space-y-2">
          {history.data.map((entry) => {
            const isExpanded = expandedId === entry.id;

            return (
              <Card key={entry.id} className="overflow-hidden">
                {/* Collapsed row */}
                <button
                  type="button"
                  className="w-full text-left px-5 py-3 flex items-center gap-3 hover:bg-gray-800/30 transition-colors"
                  onClick={() => toggleExpanded(entry.id)}
                  aria-expanded={isExpanded}
                >
                  {/* Ticker */}
                  <span className="font-mono font-bold text-white text-sm min-w-[60px]">
                    {entry.ticker}
                  </span>

                  {/* Signal badge */}
                  {signalBadge(entry.final_signal)}

                  {/* Confidence */}
                  <span className="font-mono text-sm text-gray-300">
                    {(entry.final_confidence * 100).toFixed(0)}%
                  </span>

                  {/* Regime */}
                  {regimeBadge(entry.regime)}

                  {/* Spacer */}
                  <span className="flex-1" />

                  {/* Date */}
                  <span className="text-xs text-gray-500 whitespace-nowrap">
                    {formatDate(entry.created_at)}
                  </span>

                  {/* Expand chevron */}
                  <svg
                    className={`w-4 h-4 text-gray-500 transition-transform ${
                      isExpanded ? "rotate-180" : ""
                    }`}
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>

                {/* Expanded section */}
                {isExpanded && (
                  <CardBody className="border-t border-gray-800/50">
                    {/* Reasoning */}
                    {entry.reasoning && (
                      <div className="mb-4">
                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
                          Reasoning
                        </h4>
                        <p className="text-sm text-gray-300 whitespace-pre-wrap">
                          {entry.reasoning}
                        </p>
                      </div>
                    )}

                    {/* Agent breakdown */}
                    {entry.agent_signals.length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                          Agent Breakdown
                        </h4>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-gray-500 text-xs uppercase tracking-wide">
                                <th className="text-left py-1 pr-4">Agent</th>
                                <th className="text-left py-1 pr-4">Signal</th>
                                <th className="text-left py-1">Confidence</th>
                              </tr>
                            </thead>
                            <tbody>
                              {entry.agent_signals.map((as, idx) => (
                                <tr
                                  key={idx}
                                  className="border-t border-gray-800/30"
                                >
                                  <td className="py-1.5 pr-4 text-gray-300">
                                    {as.agent_name}
                                  </td>
                                  <td className="py-1.5 pr-4">
                                    {signalBadge(as.signal)}
                                  </td>
                                  <td className="py-1.5 font-mono text-gray-300">
                                    {(as.confidence * 100).toFixed(0)}%
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Re-analyze link */}
                    <Link
                      to={`/analyze?ticker=${entry.ticker}`}
                      className="text-sm text-accent-light hover:text-accent transition-colors"
                    >
                      Re-analyze &rarr;
                    </Link>
                  </CardBody>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
