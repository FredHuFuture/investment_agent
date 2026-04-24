import type { CalibrationResponse } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import EmptyState from "../shared/EmptyState";
import { Button } from "../ui/Button";
import AgentCalibrationRow from "./AgentCalibrationRow";

interface Props {
  data: CalibrationResponse;
  onRebuildCorpus?: () => void;
  rebuildInProgress?: boolean;
}

/**
 * Canonical agent display order for the calibration table.
 * Matches KNOWN_AGENTS in api/routes/calibration.py.
 */
const AGENT_ORDER = [
  "TechnicalAgent",
  "FundamentalAgent",
  "MacroAgent",
  "SentimentAgent",
  "CryptoAgent",
  "SummaryAgent",
];

/**
 * Renders the per-agent calibration table (Brier, IC, IC-IR, sparkline).
 *
 * When corpus is empty (total_observations === 0), shows an empty-corpus CTA
 * with an optional "Rebuild corpus" button instead of the table.
 */
export default function CalibrationTable({
  data,
  onRebuildCorpus,
  rebuildInProgress,
}: Props) {
  const { agents, corpus_metadata } = data;
  const isEmpty = corpus_metadata.total_observations === 0;

  if (isEmpty) {
    return (
      <Card>
        <CardHeader title="Agent Calibration" />
        <CardBody>
          <div data-testid="cal-empty-corpus-cta" className="space-y-4 text-center py-4">
            <EmptyState message="Corpus is empty. Populate it to see per-agent calibration metrics." />
            {onRebuildCorpus && (
              <Button
                onClick={onRebuildCorpus}
                disabled={rebuildInProgress}
                data-testid="cal-rebuild-corpus-button"
              >
                {rebuildInProgress ? "Rebuilding..." : "Rebuild corpus"}
              </Button>
            )}
          </div>
        </CardBody>
      </Card>
    );
  }

  const orderedAgents = AGENT_ORDER.filter((name) => agents[name] !== undefined);

  return (
    <Card>
      <CardHeader
        title="Agent Calibration"
        subtitle={`${corpus_metadata.total_observations} observations across ${corpus_metadata.tickers_covered.length} tickers · ${data.horizon} forward horizon · ${data.window_days}-obs rolling window`}
      />
      <CardBody>
        <table className="w-full text-sm" data-testid="cal-calibration-table">
          <thead>
            <tr className="border-b border-gray-800 text-xs uppercase text-gray-500">
              <th className="text-left py-2 pr-3">Agent</th>
              <th className="text-left py-2 pr-3">Brier</th>
              <th className="text-left py-2 pr-3">IC ({data.horizon})</th>
              <th className="text-left py-2 pr-3">IC-IR</th>
              <th className="text-left py-2">90-day trend</th>
            </tr>
          </thead>
          <tbody>
            {orderedAgents.map((name) => (
              <AgentCalibrationRow
                key={name}
                agentName={name}
                entry={agents[name]!}
              />
            ))}
          </tbody>
        </table>
        {corpus_metadata.survivorship_bias_warning && (
          <p className="mt-3 text-xs text-amber-400/70">
            Note: corpus currently reflects tickers active in the backtest window; survivorship
            bias is possible. Thresholds (window 30/60/5) are preliminary and will tighten to
            qlib defaults (252/63) once live history accumulates.
          </p>
        )}
      </CardBody>
    </Card>
  );
}
