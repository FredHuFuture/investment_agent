import type { DriftLogEntry } from "../../api/types";

interface Props {
  entry: DriftLogEntry | null;
  agentName: string;
}

/**
 * Window for "drift detected" badge visibility (ROADMAP SC-5).
 * Older drift events are not surfaced as active badges — they remain in the
 * historical drift_log but the row UI returns to "OK" state.
 */
const RECENT_DRIFT_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

function fmtDelta(delta: number | null): string {
  if (delta === null || Number.isNaN(delta)) return "";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}%`;
}

/**
 * AN-02 (Phase 7): per-agent drift status badge for AgentCalibrationRow.
 *
 * States:
 *   1. preliminary_threshold=true (regardless of triggered) → amber "Preliminary"
 *      (corpus has < 60 weekly IC samples — thresholds inactive)
 *   2. triggered=true AND evaluated_at within 7 days → red "Drift Detected (delta%)"
 *   3. otherwise → renders nothing (null)
 *
 * Tooltip surfaces the threshold_type (pct_drop / absolute_floor) and the
 * 60-day average for context.
 */
export default function DriftBadge({ entry, agentName }: Props) {
  if (entry === null) return null;

  // State 1: preliminary takes precedence — even if triggered, threshold is inactive
  if (entry.preliminary_threshold) {
    return (
      <span
        data-testid={`cal-drift-badge-${agentName}`}
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide bg-amber-500/15 text-amber-300 border border-amber-500/30 ml-2"
        title="Preliminary threshold — needs 60+ weekly IC samples (run corpus rebuild)"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" aria-hidden />
        Preliminary
      </span>
    );
  }

  // State 2: triggered AND recent
  if (entry.triggered) {
    const evaluatedTime = Date.parse(entry.evaluated_at);
    const ageMs = Number.isNaN(evaluatedTime)
      ? Infinity
      : Date.now() - evaluatedTime;
    if (ageMs <= RECENT_DRIFT_WINDOW_MS) {
      const deltaText = fmtDelta(entry.delta_pct);
      const tooltip =
        entry.threshold_type === "absolute_floor"
          ? `IC-IR floor (<0.5) breached for 2 consecutive weeks`
          : `IC-IR dropped ${deltaText} below 60-day avg ${
              entry.avg_icir_60d !== null ? entry.avg_icir_60d.toFixed(2) : "—"
            }`;
      return (
        <span
          data-testid={`cal-drift-badge-${agentName}`}
          className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide bg-red-500/15 text-red-300 border border-red-500/30 ml-2"
          title={tooltip}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-red-400" aria-hidden />
          Drift Detected{deltaText ? ` (${deltaText})` : ""}
        </span>
      );
    }
  }

  // State 3: nothing to show
  return null;
}
