import { useEffect, useState } from "react";
import { getPositionSize } from "../../api/endpoints";
import type { PortfolioImpact } from "../../api/types";
import { SkeletonCard } from "../ui/Skeleton";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function barColor(key: string): string {
  if (key === "stock_pct") return "bg-blue-500";
  if (key === "crypto_pct") return "bg-orange-500";
  return "bg-gray-500"; // cash_pct
}

function barLabel(key: string): string {
  if (key === "stock_pct") return "Stock";
  if (key === "crypto_pct") return "Crypto";
  return "Cash";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Horizontal stacked bar chart showing stock/crypto/cash split. */
function ExposureBar({ exposure, label }: { exposure: Record<string, number>; label: string }) {
  const keys = ["stock_pct", "crypto_pct", "cash_pct"];
  return (
    <div>
      <div className="text-[11px] text-gray-500 mb-1">{label}</div>
      <div className="flex h-5 rounded-full overflow-hidden bg-gray-800">
        {keys.map((key) => {
          const val = exposure[key] ?? 0;
          if (val <= 0) return null;
          return (
            <div
              key={key}
              className={`${barColor(key)} transition-all`}
              style={{ width: `${(val * 100).toFixed(1)}%` }}
              title={`${barLabel(key)}: ${pct(val)}`}
            />
          );
        })}
      </div>
      <div className="flex gap-3 mt-1">
        {keys.map((key) => {
          const val = exposure[key] ?? 0;
          return (
            <span key={key} className="flex items-center gap-1 text-[10px] text-gray-500">
              <span className={`inline-block w-2 h-2 rounded-full ${barColor(key)}`} />
              {barLabel(key)} {pct(val)}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/** Sector exposure before/after comparison. */
function SectorExposure({
  currentPct,
  projectedPct,
  sector,
  warning,
}: {
  currentPct: number;
  projectedPct: number;
  sector: string | null;
  warning: string | null;
}) {
  const maxPct = Math.max(currentPct, projectedPct, 0.01);
  const scale = 100 / maxPct;

  return (
    <div className="space-y-2">
      <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500">
        Sector Exposure {sector ? `(${sector})` : ""}
      </div>
      <div className="space-y-1.5">
        <div>
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[10px] text-gray-500">Current</span>
            <span className="text-[10px] text-gray-400 font-mono">{pct(currentPct)}</span>
          </div>
          <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-blue-500/70 transition-all"
              style={{ width: `${(currentPct * scale).toFixed(1)}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[10px] text-gray-500">Projected</span>
            <span className="text-[10px] text-gray-400 font-mono">{pct(projectedPct)}</span>
          </div>
          <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${warning ? "bg-yellow-500" : "bg-emerald-500"}`}
              style={{ width: `${(projectedPct * scale).toFixed(1)}%` }}
            />
          </div>
        </div>
      </div>
      {warning && (
        <div className="rounded-lg bg-yellow-400/10 border border-yellow-400/30 px-3 py-2 text-xs text-yellow-400">
          {warning}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PortfolioImpactPanel
// ---------------------------------------------------------------------------
interface PortfolioImpactPanelProps {
  ticker: string;
  assetType?: string;
}

export default function PortfolioImpactPanel({
  ticker,
  assetType = "stock",
}: PortfolioImpactPanelProps) {
  const [data, setData] = useState<PortfolioImpact | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getPositionSize(ticker, assetType)
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
        <svg
          className="w-4 h-4 text-blue-400"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
          />
        </svg>
        Portfolio Impact Preview
      </h3>

      {/* Loading state */}
      {loading && <SkeletonCard />}

      {/* Error state */}
      {error && (
        <p className="text-gray-500 text-sm">
          Could not load portfolio impact data.
        </p>
      )}

      {/* Loaded with data */}
      {!loading && !error && data && (
        <div className="space-y-5">
          {/* Position Sizing */}
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500 mb-2">
              Position Sizing
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg bg-gray-800/30 border border-gray-700/30 px-3 py-2.5">
                <div className="text-[10px] text-gray-500 mb-0.5">Suggested Qty</div>
                <div className="text-sm font-mono text-gray-200">
                  {data.suggested_quantity !== null ? data.suggested_quantity.toLocaleString() : "--"}
                </div>
              </div>
              <div className="rounded-lg bg-gray-800/30 border border-gray-700/30 px-3 py-2.5">
                <div className="text-[10px] text-gray-500 mb-0.5">Allocation</div>
                <div className="text-sm font-mono text-gray-200">
                  {pct(data.suggested_allocation_pct)}
                </div>
              </div>
              <div className="rounded-lg bg-gray-800/30 border border-gray-700/30 px-3 py-2.5">
                <div className="text-[10px] text-gray-500 mb-0.5">Max Position</div>
                <div className="text-sm font-mono text-gray-200">
                  {pct(data.max_position_pct)}
                </div>
              </div>
            </div>
          </div>

          {/* Sector Exposure */}
          <SectorExposure
            currentPct={data.current_sector_pct}
            projectedPct={data.projected_sector_pct}
            sector={data.sector}
            warning={data.concentration_warning}
          />

          {/* Portfolio Composition: Before / After */}
          <div>
            <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500 mb-3">
              Portfolio Composition
            </div>
            <div className="space-y-3">
              <ExposureBar exposure={data.before_exposure} label="Before" />
              <ExposureBar exposure={data.after_exposure} label="After" />
            </div>
          </div>

          {/* Correlation */}
          {data.correlated_positions.length > 0 && (
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500 mb-2">
                Correlated Positions
              </div>
              <div className="rounded-lg bg-gray-800/30 border border-gray-700/30 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700/30">
                      <th className="text-left px-3 py-1.5 text-[10px] font-medium text-gray-500 uppercase">
                        Ticker
                      </th>
                      <th className="text-right px-3 py-1.5 text-[10px] font-medium text-gray-500 uppercase">
                        Correlation
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.correlated_positions.map((cp) => (
                      <tr
                        key={cp.ticker}
                        className="border-b border-gray-700/20 last:border-b-0"
                      >
                        <td className="px-3 py-1.5 font-mono text-gray-300">
                          {cp.ticker}
                        </td>
                        <td
                          className={`px-3 py-1.5 text-right font-mono ${
                            cp.correlation >= 0.8
                              ? "text-red-400"
                              : cp.correlation >= 0.5
                                ? "text-yellow-400"
                                : "text-gray-400"
                          }`}
                        >
                          {cp.correlation.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Warnings */}
          {(data.concentration_warning || data.correlation_warning) && (
            <div className="space-y-2">
              {data.correlation_warning && (
                <div className="rounded-lg bg-yellow-400/10 border border-yellow-400/30 px-3 py-2 text-xs text-yellow-400">
                  {data.correlation_warning}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* No data at all */}
      {!loading && !error && !data && (
        <div className="text-center py-6">
          <p className="text-sm text-gray-500">No portfolio impact data available</p>
        </div>
      )}
    </div>
  );
}
