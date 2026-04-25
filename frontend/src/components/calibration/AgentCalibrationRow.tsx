import type { AgentCalibrationEntry, DriftLogEntry } from "../../api/types";
import ICSparkline from "./ICSparkline";
import DriftBadge from "./DriftBadge";

interface Props {
  agentName: string;
  entry: AgentCalibrationEntry;
  driftEntry?: DriftLogEntry | null; // optional — backward-compat
}

function fmtBrier(v: number | null, sampleSize: number): { text: string; title: string } {
  if (v === null) {
    return {
      text: "Insufficient data",
      title:
        sampleSize < 20
          ? `Brier requires N >= 20 (current: ${sampleSize})`
          : "Brier unavailable for this agent in current corpus",
    };
  }
  return { text: v.toFixed(3), title: "Brier score (lower is better; 0 = perfect)" };
}

function fmtIc(
  v: number | null,
  sampleSize: number,
  label: string,
  minN: number,
): { text: string; title: string } {
  if (v === null) {
    return {
      text: "Insufficient data",
      title:
        sampleSize < minN
          ? `${label} requires N >= ${minN} (current: ${sampleSize})`
          : `${label} unavailable for this agent`,
    };
  }
  return {
    text: v.toFixed(3),
    title: `${label} (higher is better for IC; IC-IR > 0.5 is typically actionable)`,
  };
}

/**
 * Single table row for one agent in the CalibrationTable.
 * Shows agent name, Brier, IC, IC-IR, and a rolling-IC sparkline.
 * FundamentalAgent (and any NULL_EXPECTED agent) renders a full-width note
 * instead of metric cells when entry.note is present.
 */
export default function AgentCalibrationRow({ agentName, entry, driftEntry = null }: Props) {
  // FundamentalAgent FOUND-04 note branch — takes precedence over metrics
  if (entry.note) {
    return (
      <tr data-testid={`cal-agent-row-${agentName}`}>
        <td className="py-2 pr-3 font-medium text-gray-300 align-top">{agentName}</td>
        <td
          colSpan={4}
          className="py-2 text-xs text-amber-400/80 italic"
          data-testid={`cal-agent-note-${agentName}`}
        >
          {entry.note}
        </td>
      </tr>
    );
  }

  const brier = fmtBrier(entry.brier_score, entry.sample_size);
  const ic = fmtIc(entry.ic_5d, entry.sample_size, `IC (${entry.ic_horizon})`, 30);
  const icir = fmtIc(entry.ic_ir, entry.sample_size, "IC-IR", 30);

  return (
    <tr data-testid={`cal-agent-row-${agentName}`} className="border-b border-gray-800/40">
      <td className="py-2 pr-3 font-medium text-gray-200">{agentName}</td>
      <td className="py-2 pr-3 text-sm text-gray-400 font-mono" title={brier.title}>
        {brier.text}
      </td>
      <td className="py-2 pr-3 text-sm text-gray-400 font-mono" title={ic.title}>
        {ic.text}
      </td>
      <td className="py-2 pr-3 text-sm text-gray-400 font-mono" title={icir.title}>
        <span className="inline-flex items-center">
          {icir.text}
          <DriftBadge entry={driftEntry} agentName={agentName} />
        </span>
      </td>
      <td className="py-2">
        <ICSparkline
          agentName={agentName}
          rollingIc={entry.rolling_ic}
          icIr={entry.ic_ir}
        />
      </td>
    </tr>
  );
}
