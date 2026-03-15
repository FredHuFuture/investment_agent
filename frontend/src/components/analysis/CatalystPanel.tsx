import { useEffect, useState } from "react";
import { getCatalysts } from "../../api/endpoints";
import type { CatalystData } from "../../api/types";
import SignalBadge from "../shared/SignalBadge";
import LoadingSpinner from "../shared/LoadingSpinner";
import { formatRelativeDate } from "../../lib/formatters";

// ---------------------------------------------------------------------------
// Sentiment score gauge
// ---------------------------------------------------------------------------
function SentimentGauge({ score }: { score: number }) {
  // score ranges from -1.0 to +1.0, we map to 0-100% for display
  const pct = ((score + 1) / 2) * 100;
  const color =
    score > 0.2
      ? "bg-emerald-400"
      : score < -0.2
        ? "bg-red-400"
        : "bg-yellow-400";
  const label =
    score > 0.2
      ? "Positive"
      : score < -0.2
        ? "Negative"
        : "Neutral";

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-gray-500">Sentiment</span>
        <span className="text-[11px] text-gray-400 font-mono">
          {score >= 0 ? "+" : ""}
          {score.toFixed(2)} ({label})
        </span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confidence bar (takes 0-100 value directly)
// ---------------------------------------------------------------------------
function ConfidenceDisplay({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const color =
    pct >= 70 ? "bg-emerald-400" : pct >= 40 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-gray-500">Confidence</span>
        <span className="text-[11px] text-gray-400 font-mono">
          {pct.toFixed(0)}%
        </span>
      </div>
      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CatalystPanel
// ---------------------------------------------------------------------------
interface CatalystPanelProps {
  ticker: string;
  assetType?: string;
}

export default function CatalystPanel({
  ticker,
  assetType = "stock",
}: CatalystPanelProps) {
  const [data, setData] = useState<CatalystData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getCatalysts(ticker, assetType)
      .then((res) => {
        if (!cancelled) {
          setData(res.data);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [ticker, assetType]);

  return (
    <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-6">
      <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
        <span className="text-base">{"📰"}</span>
        News & Catalysts
      </h3>

      {/* Loading state */}
      {loading && (
        <div className="flex justify-center py-8">
          <LoadingSpinner />
        </div>
      )}

      {/* Error state */}
      {error && (
        <p className="text-gray-500 text-sm">
          Could not load catalyst data.
        </p>
      )}

      {/* Loaded with data */}
      {!loading && !error && data && (
        <div className="space-y-5">
          {/* Sentiment summary */}
          {data.sentiment ? (
            <div className="space-y-4">
              {/* Signal badge row */}
              <div className="flex items-center gap-3">
                <SignalBadge signal={data.sentiment.signal} />
                <span className="text-xs text-gray-500">
                  Sentiment-based signal
                </span>
              </div>

              {/* Confidence + Sentiment bars */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <ConfidenceDisplay value={data.sentiment.confidence} />
                <SentimentGauge score={data.sentiment.sentiment_score} />
              </div>

              {/* Catalysts list */}
              {data.sentiment.catalysts.length > 0 && (
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500 mb-2">
                    Key Catalysts
                  </div>
                  <ul className="space-y-1">
                    {data.sentiment.catalysts.map((c, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm text-gray-300"
                      >
                        <span className="text-emerald-400 mt-0.5 shrink-0">
                          {"•"}
                        </span>
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Reasoning */}
              {data.sentiment.reasoning && (
                <div>
                  <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500 mb-1">
                    Reasoning
                  </div>
                  <p className="text-xs text-gray-400 leading-relaxed">
                    {data.sentiment.reasoning}
                  </p>
                </div>
              )}
            </div>
          ) : (
            data.headlines.length > 0 && (
              <div className="rounded-lg bg-gray-800/30 border border-gray-700/30 px-3 py-2">
                <p className="text-xs text-gray-500">
                  Sentiment analysis unavailable (API key required)
                </p>
              </div>
            )
          )}

          {/* Headlines */}
          {data.headlines.length > 0 ? (
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500 mb-3">
                Recent Headlines
              </div>
              <div className="space-y-2">
                {data.headlines.map((h, i) => (
                  <div
                    key={i}
                    className="rounded-lg bg-gray-800/30 border border-gray-700/30 px-3 py-2.5 hover:bg-gray-800/50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        {h.url ? (
                          <a
                            href={h.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-gray-200 hover:text-white transition-colors line-clamp-2"
                          >
                            {h.title}
                          </a>
                        ) : (
                          <span className="text-sm text-gray-200 line-clamp-2">
                            {h.title}
                          </span>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-[10px] text-gray-500">
                            {h.source}
                          </span>
                          {h.published_at && (
                            <>
                              <span className="text-[10px] text-gray-700">
                                {"·"}
                              </span>
                              <span className="text-[10px] text-gray-500">
                                {formatRelativeDate(h.published_at)}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                      {h.url && (
                        <a
                          href={h.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="shrink-0 text-gray-600 hover:text-gray-400 transition-colors mt-0.5"
                          aria-label="Open article"
                        >
                          <svg
                            className="w-3.5 h-3.5"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={2}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
                            />
                          </svg>
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            !data.sentiment && (
              <div className="text-center py-6">
                <p className="text-sm text-gray-500">
                  No recent news found
                </p>
              </div>
            )
          )}
        </div>
      )}

      {/* No data at all */}
      {!loading && !error && !data && (
        <div className="text-center py-6">
          <p className="text-sm text-gray-500">No recent news found</p>
        </div>
      )}
    </div>
  );
}
