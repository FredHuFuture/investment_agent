import SignalBadge from "../shared/SignalBadge";
import ConfidenceBar from "../shared/ConfidenceBar";
import MetricCard from "../shared/MetricCard";
import AgentBreakdown from "./AgentBreakdown";
import type { AnalysisResult as AnalysisResultType } from "../../api/types";

export default function AnalysisResult({ data }: { data: AnalysisResultType }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-bold font-mono">{data.ticker}</h2>
        <SignalBadge signal={data.final_signal} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
          value={data.regime}
          sub={`${data.agent_signals.length} agents`}
        />
      </div>

      <div>
        <ConfidenceBar value={data.final_confidence / 100} />
      </div>

      <div>
        <h3 className="text-lg font-semibold mb-3">Agent Breakdown</h3>
        <AgentBreakdown agents={data.agent_signals} />
      </div>

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
