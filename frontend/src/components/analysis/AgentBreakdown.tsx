import SignalBadge from "../shared/SignalBadge";
import ConfidenceBar from "../shared/ConfidenceBar";
import type { AgentSignal } from "../../api/types";

export default function AgentBreakdown({ agents }: { agents: AgentSignal[] }) {
  return (
    <div className="space-y-3">
      {agents.map((a) => (
        <div
          key={a.agent_name}
          className="rounded-xl bg-gray-900/50 backdrop-blur-sm border border-gray-800/50 p-4"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold text-sm">{a.agent_name}</span>
            <div className="flex items-center gap-2">
              <SignalBadge signal={a.signal} />
              <span className="text-xs text-gray-500 font-mono">
                {a.confidence.toFixed(1)}%
              </span>
            </div>
          </div>
          <ConfidenceBar value={a.confidence / 100} />
          <p className="mt-2 text-xs text-gray-400 leading-relaxed">
            {a.reasoning}
          </p>
          {a.metrics && Object.keys(a.metrics).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(a.metrics)
                .filter(([, v]) => typeof v === "number")
                .slice(0, 8)
                .map(([k, v]) => (
                  <span
                    key={k}
                    className="text-xs bg-gray-800 px-2 py-0.5 rounded"
                  >
                    {k}: <span className="font-mono">{v.toFixed(2)}</span>
                  </span>
                ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
