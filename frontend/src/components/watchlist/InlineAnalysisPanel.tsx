import type { AnalysisResult } from "../../api/types";
import SignalBadge from "../shared/SignalBadge";
import { Button } from "../ui/Button";

interface InlineAnalysisPanelProps {
  analysis: AnalysisResult;
  onClose: () => void;
}

/** Signal dot color mapping */
const dotColor: Record<string, string> = {
  BUY: "bg-green-400",
  SELL: "bg-red-400",
  HOLD: "bg-gray-400",
};

export default function InlineAnalysisPanel({
  analysis,
  onClose,
}: InlineAnalysisPanelProps) {
  const reasoning =
    analysis.reasoning.length > 120
      ? analysis.reasoning.slice(0, 120) + "..."
      : analysis.reasoning;

  return (
    <tr>
      <td colSpan={10} className="px-4 py-0">
        <div className="bg-gray-800/60 border border-gray-700/50 rounded-lg p-4 my-2">
          <div className="flex items-start justify-between gap-4">
            {/* Left: signal + confidence + reasoning */}
            <div className="flex-1 min-w-0 space-y-2">
              <div className="flex items-center gap-3">
                <SignalBadge signal={analysis.final_signal} />
                <span className="text-sm text-gray-300">
                  {analysis.final_confidence.toFixed(1)}% confidence
                </span>
                <span className="text-xs text-gray-500">
                  Regime: {analysis.regime}
                </span>
              </div>

              <p className="text-sm text-gray-400 leading-relaxed">
                {reasoning}
              </p>

              {/* Agent signal breakdown dots */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-gray-500 mr-1">Agents:</span>
                {analysis.agent_signals.map((as) => (
                  <div
                    key={as.agent_name}
                    className="flex items-center gap-1"
                    title={`${as.agent_name}: ${as.signal} (${as.confidence.toFixed(0)}%)`}
                  >
                    <span
                      className={`inline-block w-2.5 h-2.5 rounded-full ${dotColor[as.signal.toUpperCase()] ?? "bg-gray-500"}`}
                    />
                    <span className="text-xs text-gray-500">
                      {as.agent_name.replace(/_agent$/i, "")}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Close button */}
            <Button variant="ghost" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </td>
    </tr>
  );
}
