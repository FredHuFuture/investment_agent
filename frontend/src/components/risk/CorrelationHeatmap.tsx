import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { getPortfolioCorrelations } from "../../api/endpoints";
import type { CorrelationData } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

/** Returns a CSS background color based on correlation value. */
function cellBgColor(value: number, isDiagonal: boolean): string {
  if (isDiagonal) return "rgb(55, 65, 81)"; // gray-700

  // Positive correlations -> red scale, negative -> blue scale
  const abs = Math.abs(value);
  if (value >= 0.7) return `rgba(239, 68, 68, ${0.25 + abs * 0.35})`; // dark red
  if (value >= 0.3) return `rgba(239, 68, 68, ${0.10 + abs * 0.15})`; // light red
  if (value > -0.3) return "rgba(156, 163, 175, 0.08)"; // neutral
  if (value > -0.7) return `rgba(59, 130, 246, ${0.10 + abs * 0.15})`; // light blue
  return `rgba(59, 130, 246, ${0.25 + abs * 0.35})`; // dark blue
}

/** Returns text color for a cell. */
function cellTextColor(value: number, isDiagonal: boolean): string {
  if (isDiagonal) return "rgb(156, 163, 175)"; // gray-400
  const abs = Math.abs(value);
  if (abs >= 0.7) return value > 0 ? "rgb(252, 165, 165)" : "rgb(147, 197, 253)"; // red-300 / blue-300
  if (abs >= 0.3) return value > 0 ? "rgb(253, 186, 116)" : "rgb(147, 197, 253)"; // amber-300 / blue-300
  return "rgb(209, 213, 219)"; // gray-300
}

/** Badge color class for concentration risk. */
function concentrationBadgeClass(risk: CorrelationData["concentration_risk"]): string {
  if (risk === "HIGH") return "bg-red-500/20 text-red-400 border border-red-500/30";
  if (risk === "MODERATE") return "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30";
  return "bg-green-500/20 text-green-400 border border-green-500/30";
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

interface TooltipState {
  x: number;
  y: number;
  label: string;
}

function HeatmapTooltip({ tooltip }: { tooltip: TooltipState }) {
  return (
    <div
      className="fixed z-50 pointer-events-none bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-lg whitespace-nowrap"
      style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
    >
      {tooltip.label}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function CorrelationHeatmap() {
  const { data, loading, error, refetch } = useApi<CorrelationData>(
    () => getPortfolioCorrelations(90),
    { cacheKey: "risk:correlation-heatmap", ttlMs: 120_000 },
  );

  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  // Handle error response embedded in data
  const dataError =
    data && "error" in data ? (data as unknown as { error: string }).error : null;

  if (loading) return <SkeletonCard className="h-[340px]" />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  if (dataError) {
    return (
      <Card>
        <CardHeader
          title="Correlation Matrix"
          subtitle="Pairwise asset correlation heatmap"
        />
        <CardBody>
          <p className="text-sm text-gray-500">{dataError}</p>
        </CardBody>
      </Card>
    );
  }

  if (!data || data.tickers.length < 2) {
    return (
      <Card>
        <CardHeader
          title="Correlation Matrix"
          subtitle="Pairwise asset correlation heatmap"
        />
        <CardBody>
          <p className="text-sm text-gray-500">
            Portfolio requires at least 2 positions with sufficient price history to
            display correlations.
          </p>
        </CardBody>
      </Card>
    );
  }

  const { tickers, correlation_matrix, concentration_risk, high_correlation_pairs, avg_correlation } = data;

  /** Look up correlation between two tickers. */
  function getCorr(t1: string, t2: string): number {
    if (t1 === t2) return 1;
    const key1 = `${t1}:${t2}`;
    const key2 = `${t2}:${t1}`;
    if (correlation_matrix[key1] !== undefined) return correlation_matrix[key1];
    if (correlation_matrix[key2] !== undefined) return correlation_matrix[key2];
    return 0;
  }

  // Grid template: first column for row headers, then one column per ticker
  const gridTemplateColumns = `minmax(56px, auto) repeat(${tickers.length}, minmax(56px, 1fr))`;

  function handleCellMouse(
    e: React.MouseEvent,
    row: string,
    col: string,
    value: number,
  ) {
    setTooltip({
      x: e.clientX,
      y: e.clientY,
      label: `${row} vs ${col}: ${value.toFixed(2)}`,
    });
  }

  return (
    <Card>
      <CardHeader
        title="Correlation Matrix"
        subtitle="Pairwise asset correlation heatmap"
      />
      <CardBody>
        <div className="space-y-4">
          {/* Heatmap grid */}
          <div className="overflow-x-auto">
            <div
              className="inline-grid gap-px text-xs"
              style={{ gridTemplateColumns }}
            >
              {/* Top-left empty corner */}
              <div />

              {/* Column headers */}
              {tickers.map((t) => (
                <div
                  key={`col-${t}`}
                  className="px-1 py-1.5 text-center font-mono font-medium text-gray-400 truncate"
                  title={t}
                >
                  {t}
                </div>
              ))}

              {/* Rows */}
              {tickers.map((rowTicker) => (
                <>
                  {/* Row header */}
                  <div
                    key={`row-${rowTicker}`}
                    className="pr-2 py-1.5 text-right font-mono font-medium text-gray-400 whitespace-nowrap self-center"
                  >
                    {rowTicker}
                  </div>

                  {/* Data cells */}
                  {tickers.map((colTicker) => {
                    const isDiag = rowTicker === colTicker;
                    const val = getCorr(rowTicker, colTicker);
                    return (
                      <div
                        key={`${rowTicker}-${colTicker}`}
                        className="px-1 py-1.5 text-center rounded cursor-default transition-opacity hover:opacity-80"
                        style={{
                          backgroundColor: cellBgColor(val, isDiag),
                          color: cellTextColor(val, isDiag),
                        }}
                        onMouseMove={(e) =>
                          handleCellMouse(e, rowTicker, colTicker, val)
                        }
                        onMouseLeave={() => setTooltip(null)}
                      >
                        {val.toFixed(2)}
                      </div>
                    );
                  })}
                </>
              ))}
            </div>
          </div>

          {/* Legend */}
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span className="font-medium">Scale:</span>
            <div className="flex items-center gap-1">
              <div
                className="w-4 h-3 rounded"
                style={{ backgroundColor: "rgba(59, 130, 246, 0.60)" }}
              />
              <span>-1.0</span>
            </div>
            <div className="flex items-center gap-1">
              <div
                className="w-4 h-3 rounded"
                style={{ backgroundColor: "rgba(156, 163, 175, 0.08)" }}
              />
              <span>0</span>
            </div>
            <div className="flex items-center gap-1">
              <div
                className="w-4 h-3 rounded"
                style={{ backgroundColor: "rgba(239, 68, 68, 0.60)" }}
              />
              <span>+1.0</span>
            </div>
          </div>

          {/* Stats row: avg correlation + concentration risk badge */}
          <div className="flex flex-wrap items-center gap-4 pt-3 border-t border-gray-800/50">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 uppercase tracking-wider">
                Avg Correlation
              </span>
              <span className="text-sm font-semibold text-gray-300">
                {(avg_correlation * 100).toFixed(1)}%
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 uppercase tracking-wider">
                Concentration Risk
              </span>
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${concentrationBadgeClass(concentration_risk)}`}
              >
                {concentration_risk}
              </span>
            </div>
          </div>

          {/* High correlation pairs */}
          {high_correlation_pairs.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs text-gray-500 uppercase tracking-wider">
                High Correlation Pairs
              </p>
              {high_correlation_pairs.map(([t1, t2, corr]) => (
                <div
                  key={`${t1}-${t2}`}
                  className="flex items-center gap-2 text-xs text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2"
                >
                  <svg
                    className="w-3.5 h-3.5 shrink-0"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                    <path d="M12 9v4" />
                    <path d="M12 17h.01" />
                  </svg>
                  <span>
                    <span className="font-mono font-semibold">{t1}</span>
                    {" & "}
                    <span className="font-mono font-semibold">{t2}</span>
                    {" — correlation: "}
                    <span className="font-semibold">
                      {(corr * 100).toFixed(1)}%
                    </span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Floating tooltip */}
        {tooltip && <HeatmapTooltip tooltip={tooltip} />}
      </CardBody>
    </Card>
  );
}
