import { useState } from "react";
import type { WeightsOverviewResponse } from "../../api/types";
import { Card, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import type { AssetType } from "./AssetTypeTabs";

interface Props {
  data: WeightsOverviewResponse;
  assetType: AssetType;
  onApplyIcIr: () => Promise<void>;
  onOverride: (agent: string, excluded: boolean) => Promise<void>;
  applying: boolean;
}

function sourceBadgeColor(source: string): string {
  if (source === "ic_ir") return "bg-green-500/20 text-green-400 border-green-500/30";
  if (source === "manual") return "bg-amber-500/20 text-amber-400 border-amber-500/30";
  return "bg-gray-700/40 text-gray-400 border-gray-700";
}

function sourceBadgeLabel(source: string): string {
  if (source === "ic_ir") return "IC-IR";
  if (source === "manual") return "Manual";
  return "Default";
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function fmtDelta(
  current: number | undefined,
  suggested: number | null | undefined,
): string {
  if (current === undefined || suggested === null || suggested === undefined) return "--";
  const delta = (suggested - current) * 100;
  const sign = delta >= 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}pp`;
}

/**
 * Renders per-agent weights editor: Current | Suggested (IC-IR) | Delta | Exclude toggle.
 * "Apply IC-IR weights" button is disabled when suggested_ic_ir for the active asset type is null.
 * Per-agent exclude toggle calls onOverride callback; pending state prevents double-click.
 */
export default function WeightsEditor({
  data,
  assetType,
  onApplyIcIr,
  onOverride,
  applying,
}: Props) {
  const current = data.current[assetType] ?? {};
  const suggested = data.suggested_ic_ir[assetType];
  const overrides = data.overrides[assetType] ?? {};

  const agents = Array.from(
    new Set([
      ...Object.keys(current),
      ...Object.keys(suggested ?? {}),
      ...Object.keys(overrides),
    ]),
  );

  const applyDisabled = suggested === null || applying;
  const applyTooltip =
    suggested === null
      ? "IC-IR suggestions unavailable — populate corpus first"
      : "Persist the IC-IR-derived weights to the aggregator";

  const [pending, setPending] = useState<Set<string>>(new Set());

  async function handleToggle(agent: string, excluded: boolean) {
    setPending((p) => new Set(p).add(agent));
    try {
      await onOverride(agent, excluded);
    } finally {
      setPending((p) => {
        const next = new Set(p);
        next.delete(agent);
        return next;
      });
    }
  }

  return (
    <div data-testid="cal-weights-editor">
    <Card>
      {/* Custom header — subtitle contains JSX badge, cannot use CardHeader subtitle prop (string only) */}
      <div className="px-4 sm:px-5 py-3.5 border-b border-gray-800/40 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-200">Agent Weights</h3>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-gray-500">Source:</span>
            <span
              data-testid="cal-weights-source-badge"
              className={`px-2 py-0.5 text-xs rounded border ${sourceBadgeColor(data.source)}`}
            >
              {sourceBadgeLabel(data.source)}
            </span>
            {data.sample_size > 0 && (
              <span className="text-xs text-gray-600">
                ({data.sample_size} samples)
              </span>
            )}
          </div>
        </div>
        <Button
          onClick={() => void onApplyIcIr()}
          disabled={applyDisabled}
          title={applyTooltip}
          data-testid="cal-apply-ic-ir-button"
        >
          {applying ? "Applying..." : "Apply IC-IR weights"}
        </Button>
      </div>
      <CardBody>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-xs uppercase text-gray-500">
              <th className="text-left py-2 pr-3">Agent</th>
              <th className="text-left py-2 pr-3">Current</th>
              <th className="text-left py-2 pr-3">Suggested (IC-IR)</th>
              <th className="text-left py-2 pr-3">Delta</th>
              <th className="text-left py-2">Exclude</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => {
              const cur = current[agent];
              const sug = suggested?.[agent] ?? null;
              const ov = overrides[agent];
              const excluded = ov?.excluded ?? false;
              return (
                <tr
                  key={agent}
                  data-testid={`cal-weights-row-${assetType}-${agent}`}
                  className="border-b border-gray-800/40"
                >
                  <td className="py-2 pr-3 font-medium text-gray-200">
                    {agent}
                    {ov?.manual_override && (
                      <span className="ml-2 text-[10px] text-amber-400/70 uppercase">
                        manual
                      </span>
                    )}
                  </td>
                  <td
                    className="py-2 pr-3 text-sm text-gray-400 font-mono"
                    data-testid={`cal-current-${assetType}-${agent}`}
                  >
                    {fmtPct(cur)}
                  </td>
                  <td className="py-2 pr-3 text-sm text-gray-400 font-mono">
                    {fmtPct(sug)}
                  </td>
                  <td className="py-2 pr-3 text-sm text-gray-500 font-mono">
                    {fmtDelta(cur, sug)}
                  </td>
                  <td className="py-2">
                    <label className="inline-flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={excluded}
                        disabled={pending.has(agent)}
                        onChange={(e) => void handleToggle(agent, e.target.checked)}
                        data-testid={`cal-exclude-toggle-${assetType}-${agent}`}
                        className="accent-amber-500"
                      />
                      <span className="text-xs text-gray-500">
                        {excluded ? "Excluded" : "Active"}
                      </span>
                    </label>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardBody>
    </Card>
    </div>
  );
}
