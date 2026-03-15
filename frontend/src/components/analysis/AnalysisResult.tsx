import { Suspense, lazy, useState, useCallback } from "react";
import SignalBadge from "../shared/SignalBadge";
import MetricCard from "../shared/MetricCard";
import { Button } from "../ui/Button";
import { SkeletonCard } from "../ui/Skeleton";
import AgentBreakdown from "./AgentBreakdown";
import CatalystPanel from "./CatalystPanel";
import KeyMetricsPanel from "./KeyMetricsPanel";
import PortfolioImpactPanel from "./PortfolioImpactPanel";
import type { AnalysisResult as AnalysisResultType } from "../../api/types";

const PriceHistoryChart = lazy(() => import("./PriceHistoryChart"));

function formatRegime(raw: string): string {
  if (!raw) return "-";
  return raw
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

/** Build a plain-text summary of the analysis for clipboard. */
function buildCopyText(data: AnalysisResultType): string {
  const agentSummaries = data.agent_signals
    .map((a) => `${a.agent_name}: ${a.signal} (${a.confidence.toFixed(0)}%)`)
    .join(", ");

  return [
    `${data.ticker} | ${data.final_signal.toUpperCase()} (${data.final_confidence.toFixed(1)}%) | Regime: ${formatRegime(data.regime)}`,
    `Agents: ${agentSummaries}`,
    data.reasoning,
  ].join("\n");
}

// ---------------------------------------------------------------------------
// Signal strength bar: shows raw_score position between sell and buy thresholds
// ---------------------------------------------------------------------------
function SignalStrengthBar({ rawScore }: { rawScore: number }) {
  // Fixed thresholds matching the orchestrator
  const sellThreshold = -0.3;
  const buyThreshold = 0.3;

  // Clamp raw score for display purposes (allow a little overshoot)
  const displayMin = -0.5;
  const displayMax = 0.5;
  const clamped = Math.max(displayMin, Math.min(displayMax, rawScore));

  // Position as a percentage across the bar (0% = displayMin, 100% = displayMax)
  const pct = ((clamped - displayMin) / (displayMax - displayMin)) * 100;

  // Threshold positions
  const sellPct = ((sellThreshold - displayMin) / (displayMax - displayMin)) * 100;
  const buyPct = ((buyThreshold - displayMin) / (displayMax - displayMin)) * 100;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[10px] text-gray-500">
        <span>SELL</span>
        <span>HOLD</span>
        <span>BUY</span>
      </div>
      <div className="relative h-3 rounded-full overflow-hidden bg-gray-800">
        {/* Gradient bar */}
        <div
          className="absolute inset-0 rounded-full"
          style={{
            background:
              "linear-gradient(to right, #ef4444 0%, #f59e0b 40%, #eab308 50%, #f59e0b 60%, #22c55e 100%)",
          }}
        />
        {/* Sell threshold marker */}
        <div
          className="absolute top-0 h-full w-px bg-gray-300/40"
          style={{ left: `${sellPct}%` }}
        />
        {/* Buy threshold marker */}
        <div
          className="absolute top-0 h-full w-px bg-gray-300/40"
          style={{ left: `${buyPct}%` }}
        />
        {/* Needle / marker */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 border-white bg-gray-950 shadow-lg shadow-black/40 z-10"
          style={{ left: `${pct}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-[10px] text-gray-500 font-mono">
        <span>{sellThreshold.toFixed(2)}</span>
        <span className="text-gray-300 text-xs font-semibold">
          {rawScore.toFixed(3)}
        </span>
        <span>{buyThreshold.toFixed(2)}</span>
      </div>
    </div>
  );
}

export default function AnalysisResult({ data }: { data: AnalysisResultType }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    const text = buildCopyText(data);
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [data]);

  return (
    <div className="space-y-6">
      {/* Header: ticker + signal + copy button */}
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold font-mono">{data.ticker}</h2>
        <SignalBadge signal={data.final_signal} />
        <div className="ml-auto">
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            {copied ? "Copied!" : "Copy Analysis"}
          </Button>
        </div>
      </div>

      {/* Signal strength bar */}
      <SignalStrengthBar rawScore={data.metrics.raw_score} />

      {/* Metrics row — full width */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Signal" value={data.final_signal} />
        <MetricCard
          label="Confidence"
          value={`${data.final_confidence.toFixed(1)}%`}
        />
        <MetricCard
          label="Raw Score"
          value={data.metrics.raw_score.toFixed(3)}
        />
        <MetricCard
          label="Regime"
          value={formatRegime(data.regime)}
          sub={`${data.agent_signals.length} agents`}
        />
      </div>

      {/* Price History Chart — full width */}
      <div className="rounded-xl bg-gray-800/20 border border-gray-800/50 p-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Price History
        </h3>
        <Suspense fallback={<SkeletonCard className="h-64" />}>
          <PriceHistoryChart ticker={data.ticker} assetType={data.asset_type} />
        </Suspense>
      </div>

      {/* Key Metrics — full width, multi-column grid */}
      <div className="rounded-xl bg-gray-800/20 border border-gray-800/50 p-5">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
          Key Metrics
        </h3>
        <KeyMetricsPanel
          tickerInfo={data.ticker_info}
          agentSignals={data.agent_signals}
        />
      </div>

      {/* News & Catalysts */}
      <CatalystPanel ticker={data.ticker} assetType={data.asset_type} />

      {/* Portfolio Impact Preview */}
      <PortfolioImpactPanel ticker={data.ticker} assetType={data.asset_type} />

      {/* Agent Breakdown */}
      <div>
        <h3 className="text-sm font-semibold text-gray-400 mb-3">Agent Breakdown</h3>
        <AgentBreakdown agents={data.agent_signals} />
      </div>

      {/* Warnings */}
      {data.warnings.length > 0 && (
        <div className="rounded-lg bg-yellow-400/10 border border-yellow-400/30 px-4 py-3 text-sm text-yellow-400">
          {data.warnings.map((w, i) => (
            <div key={i}>{w}</div>
          ))}
        </div>
      )}
    </div>
  );
}
