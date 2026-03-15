import { useState, useCallback } from "react";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

const AGENT_COLORS: Record<string, string> = {
  TechnicalAgent: "#3B82F6",
  FundamentalAgent: "#10B981",
  MacroAgent: "#F59E0B",
  CryptoAgent: "#8B5CF6",
};

const DEFAULT_STOCK_WEIGHTS: Record<string, number> = {
  TechnicalAgent: 0.30,
  FundamentalAgent: 0.45,
  MacroAgent: 0.25,
};

const DEFAULT_CRYPTO_WEIGHTS: Record<string, number> = {
  CryptoAgent: 1.0,
};

interface Props {
  assetType: string;
  onApply: (weights: Record<string, number>) => void;
  loading?: boolean;
}

export default function WeightAdjuster({ assetType, onApply, loading }: Props) {
  const defaults = assetType === "crypto" ? DEFAULT_CRYPTO_WEIGHTS : DEFAULT_STOCK_WEIGHTS;
  const [weights, setWeights] = useState<Record<string, number>>(defaults);
  const [expanded, setExpanded] = useState(false);

  const isCrypto = assetType === "crypto";
  const agents = Object.keys(weights);
  const total = Object.values(weights).reduce((s, v) => s + v, 0);

  // Reset weights when asset type changes
  const resetWeights = useCallback(() => {
    setWeights(assetType === "crypto" ? DEFAULT_CRYPTO_WEIGHTS : DEFAULT_STOCK_WEIGHTS);
  }, [assetType]);

  function handleSlider(agent: string, rawVal: number) {
    const others = agents.filter((a) => a !== agent);
    const otherTotal = others.reduce((s, a) => s + (weights[a] ?? 0), 0);

    const newVal = Math.max(0, Math.min(1, rawVal));
    const remaining = 1 - newVal;

    const newWeights = { ...weights, [agent]: newVal };

    // Redistribute remaining among others proportionally
    if (otherTotal > 0) {
      for (const a of others) {
        newWeights[a] = ((weights[a] ?? 0) / otherTotal) * remaining;
      }
    } else if (others.length > 0) {
      const each = remaining / others.length;
      for (const a of others) {
        newWeights[a] = each;
      }
    }

    setWeights(newWeights);
  }

  if (isCrypto) return null; // Crypto only has CryptoAgent at 100%

  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
      >
        <span className="font-medium">Custom Agent Weights</span>
        <svg
          className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          {/* Stacked bar preview */}
          <div className="h-3 rounded-full overflow-hidden flex">
            {agents.map((a) => (
              <div
                key={a}
                style={{
                  width: `${((weights[a] ?? 0) / Math.max(total, 0.01)) * 100}%`,
                  backgroundColor: AGENT_COLORS[a] ?? "#6b7280",
                }}
                className="transition-all duration-150 first:rounded-l-full last:rounded-r-full"
              />
            ))}
          </div>

          {/* Sliders */}
          {agents.map((a) => (
            <div key={a} className="flex items-center gap-3">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: AGENT_COLORS[a] ?? "#6b7280" }}
              />
              <span className="text-xs text-gray-400 w-28 truncate">{a}</span>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round((weights[a] ?? 0) * 100)}
                onChange={(e) => handleSlider(a, parseInt(e.target.value) / 100)}
                className="flex-1 h-1 accent-blue-500 cursor-pointer"
              />
              <span className="text-xs font-mono text-gray-400 w-10 text-right tabular-nums">
                {Math.round((weights[a] ?? 0) * 100)}%
              </span>
            </div>
          ))}

          <div className="flex items-center gap-2 pt-1">
            <Button
              size="sm"
              onClick={() => onApply(weights)}
              loading={loading}
            >
              Re-analyze
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={resetWeights}
            >
              Reset defaults
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
