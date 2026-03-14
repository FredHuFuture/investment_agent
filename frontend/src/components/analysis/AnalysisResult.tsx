import SignalBadge from "../shared/SignalBadge";
import MetricCard from "../shared/MetricCard";
import AgentBreakdown from "./AgentBreakdown";
import KeyMetricsPanel from "./KeyMetricsPanel";
import PriceHistoryChart from "./PriceHistoryChart";
import type { AnalysisResult as AnalysisResultType } from "../../api/types";

function formatRegime(raw: string): string {
  if (!raw) return "-";
  return raw
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

export default function AnalysisResult({ data }: { data: AnalysisResultType }) {
  return (
    <div className="space-y-6">
      {/* Header: ticker + signal */}
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold font-mono">{data.ticker}</h2>
        <SignalBadge signal={data.final_signal} />
      </div>

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
        <PriceHistoryChart ticker={data.ticker} assetType={data.asset_type} />
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
