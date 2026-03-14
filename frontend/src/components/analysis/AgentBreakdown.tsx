import { useMemo } from "react";
import SignalBadge from "../shared/SignalBadge";
import ConfidenceBar from "../shared/ConfidenceBar";
import type { AgentSignal } from "../../api/types";

// Agent color palette
const AGENT_COLORS: Record<string, string> = {
  TechnicalAgent: "#3B82F6",
  FundamentalAgent: "#10B981",
  MacroAgent: "#F59E0B",
  CryptoAgent: "#8B5CF6",
};
const FALLBACK_COLORS = ["#06B6D4", "#EC4899", "#EF4444", "#6366F1"];

function getAgentColor(name: string, idx: number): string {
  return AGENT_COLORS[name] ?? FALLBACK_COLORS[idx % FALLBACK_COLORS.length] ?? "#6b7280";
}

// ---------------------------------------------------------------------------
// SVG donut for agent weight distribution
// ---------------------------------------------------------------------------
function AgentDonut({ agents }: { agents: AgentSignal[] }) {
  const total = agents.reduce((s, a) => s + a.confidence, 0);
  if (total === 0) return null;

  const size = 100;
  const cx = size / 2;
  const cy = size / 2;
  const r = 36;
  const strokeW = 10;
  const circumference = 2 * Math.PI * r;

  let offset = 0;
  const segments = agents.map((a, i) => {
    const pct = a.confidence / total;
    const dashLen = pct * circumference;
    const dashGap = circumference - dashLen;
    const seg = (
      <circle
        key={a.agent_name}
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={getAgentColor(a.agent_name, i)}
        strokeWidth={strokeW}
        strokeDasharray={`${dashLen} ${dashGap}`}
        strokeDashoffset={-offset}
        className="transition-all duration-300"
      />
    );
    offset += dashLen;
    return seg;
  });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0 -rotate-90">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1f2937" strokeWidth={strokeW} />
      {segments}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function AgentBreakdown({ agents }: { agents: AgentSignal[] }) {
  const total = useMemo(() => agents.reduce((s, a) => s + a.confidence, 0), [agents]);

  return (
    <div className="space-y-4">
      {/* Donut + legend row */}
      <div className="flex items-center gap-6">
        <AgentDonut agents={agents} />
        <div className="flex-1 space-y-1.5">
          {agents.map((a, i) => {
            const pct = total > 0 ? (a.confidence / total) * 100 : 0;
            return (
              <div key={a.agent_name} className="flex items-center gap-2.5">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: getAgentColor(a.agent_name, i) }}
                />
                <span className="text-sm text-gray-200 flex-1">{a.agent_name}</span>
                <SignalBadge signal={a.signal} />
                <span className="text-sm font-mono text-gray-400 tabular-nums w-12 text-right">
                  {pct.toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Agent detail cards */}
      {agents.map((a) => (
        <div
          key={a.agent_name}
          className="rounded-lg bg-gray-800/30 border border-gray-800/50 px-4 py-3"
        >
          <div className="flex items-center justify-between mb-1.5">
            <span className="font-semibold text-sm text-gray-300">{a.agent_name}</span>
            <span className="text-xs text-gray-500 font-mono">
              {a.confidence.toFixed(1)}%
            </span>
          </div>
          <ConfidenceBar value={a.confidence / 100} />
          <p className="mt-2 text-xs text-gray-500 leading-relaxed">
            {a.reasoning}
          </p>
          {a.metrics && Object.keys(a.metrics).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {Object.entries(a.metrics)
                .filter(([, v]) => typeof v === "number")
                .slice(0, 8)
                .map(([k, v]) => (
                  <span
                    key={k}
                    className="text-[10px] bg-gray-800/60 text-gray-500 px-1.5 py-0.5 rounded"
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
