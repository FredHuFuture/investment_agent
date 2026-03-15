import type { AnalysisResult } from "../../api/types";
import { Card, CardBody } from "../ui/Card";
import SignalBadge from "../shared/SignalBadge";
import { signalColor } from "../../lib/colors";

interface Props {
  results: Record<string, AnalysisResult>;
  tickers: string[];
}

/** Dot colored by signal direction. */
function SignalDot({ signal }: { signal: string }) {
  const colorMap: Record<string, string> = {
    BUY: "bg-green-400",
    SELL: "bg-red-400",
    HOLD: "bg-yellow-400",
  };
  const bg = colorMap[signal.toUpperCase()] ?? "bg-gray-500";
  return <span className={`inline-block w-2 h-2 rounded-full ${bg}`} />;
}

/**
 * Determine which ticker column is "best": highest confidence among BUY signals.
 */
function findBestTicker(
  activeTickers: string[],
  results: Record<string, AnalysisResult>,
): string | null {
  let best: string | null = null;
  let bestConfidence = -1;
  for (const t of activeTickers) {
    const r = results[t];
    if (
      r &&
      r.final_signal.toUpperCase() === "BUY" &&
      r.final_confidence > bestConfidence
    ) {
      best = t;
      bestConfidence = r.final_confidence;
    }
  }
  return best;
}

export default function ComparisonResultRow({ results, tickers }: Props) {
  const activeTickers = tickers.filter((t) => results[t] !== undefined);

  if (activeTickers.length === 0) return null;

  const bestTicker = findBestTicker(activeTickers, results);

  /** All unique agent names across results. */
  const agentNames = Array.from(
    new Set(
      activeTickers.flatMap(
        (t) => results[t]?.agent_signals.map((a) => a.agent_name) ?? [],
      ),
    ),
  ).sort();

  type RowDef = {
    label: string;
    render: (r: AnalysisResult) => React.ReactNode;
  };

  const rows: RowDef[] = [
    {
      label: "Signal",
      render: (r) => <SignalBadge signal={r.final_signal} />,
    },
    {
      label: "Confidence",
      render: (r) => (
        <span className="text-gray-100">{r.final_confidence}%</span>
      ),
    },
    {
      label: "Raw Score",
      render: (r) => (
        <span className="text-gray-300 font-mono">
          {r.metrics.raw_score.toFixed(3)}
        </span>
      ),
    },
    {
      label: "Regime",
      render: (r) => (
        <span className="text-gray-300 capitalize">{r.regime}</span>
      ),
    },
    {
      label: "Consensus",
      render: (r) => (
        <span className="text-gray-300 font-mono">
          {r.metrics.consensus_score.toFixed(3)}
        </span>
      ),
    },
    // Agent breakdown rows
    ...agentNames.map((agent) => ({
      label: agent,
      render: (r: AnalysisResult) => {
        const agentSignal = r.agent_signals.find(
          (a) => a.agent_name === agent,
        );
        if (!agentSignal) {
          return <span className="text-gray-600">--</span>;
        }
        const color =
          signalColor[agentSignal.signal.toUpperCase()] ?? "text-gray-400";
        return (
          <span className="inline-flex items-center gap-1.5">
            <SignalDot signal={agentSignal.signal} />
            <span className={`text-xs font-medium ${color}`}>
              {agentSignal.signal.toUpperCase()}
            </span>
          </span>
        );
      },
    })),
  ];

  return (
    <Card>
      <CardBody>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-gray-900 text-left text-xs text-gray-500 font-medium px-3 py-2 min-w-[140px]">
                  Metric
                </th>
                {activeTickers.map((t) => (
                  <th
                    key={t}
                    className={`text-center text-xs font-semibold text-gray-200 px-4 py-2 ${
                      t === bestTicker
                        ? "border-l-2 border-emerald-400"
                        : ""
                    }`}
                  >
                    {t}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr
                  key={row.label}
                  className={idx % 2 === 0 ? "bg-gray-800/30" : ""}
                >
                  <td className="sticky left-0 z-10 bg-gray-900 text-gray-400 text-xs font-medium px-3 py-2 whitespace-nowrap">
                    {row.label}
                  </td>
                  {activeTickers.map((t) => (
                    <td
                      key={t}
                      className={`text-center px-4 py-2 ${
                        t === bestTicker
                          ? "border-l-2 border-emerald-400"
                          : ""
                      }`}
                    >
                      {row.render(results[t]!)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardBody>
    </Card>
  );
}
