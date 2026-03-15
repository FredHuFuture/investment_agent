import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { getStressScenarios } from "../../api/endpoints";
import type { StressScenario } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";

// ---------------------------------------------------------------------------
// Per-scenario expandable row
// ---------------------------------------------------------------------------

function ScenarioRow({ scenario }: { scenario: StressScenario }) {
  const [expanded, setExpanded] = useState(false);

  const impactColor =
    scenario.portfolio_impact_pct <= 0 ? "text-red-400" : "text-emerald-400";

  return (
    <div className="border-b border-gray-800/50 last:border-b-0">
      {/* Summary row */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-800/30 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-200 truncate">
            {scenario.name}
          </p>
          <p className="text-xs text-gray-500 mt-0.5 truncate">
            {scenario.description}
          </p>
        </div>

        <div className="flex items-center gap-3 ml-4 shrink-0">
          <span className={`text-sm font-bold ${impactColor}`}>
            {scenario.portfolio_impact_pct > 0 ? "+" : ""}
            {scenario.portfolio_impact_pct.toFixed(2)}%
          </span>

          {/* Chevron */}
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform duration-200 ${
              expanded ? "rotate-180" : ""
            }`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && scenario.affected_positions.length > 0 && (
        <div className="px-4 pb-3">
          <div className="bg-gray-800/40 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 uppercase tracking-wider">
                  <th className="text-left px-3 py-2 font-medium">Ticker</th>
                  <th className="text-right px-3 py-2 font-medium">Impact</th>
                </tr>
              </thead>
              <tbody>
                {scenario.affected_positions.map((pos) => {
                  const posColor =
                    pos.impact_pct <= 0 ? "text-red-400" : "text-emerald-400";
                  return (
                    <tr
                      key={pos.ticker}
                      className="border-t border-gray-700/30"
                    >
                      <td className="px-3 py-1.5 font-mono text-gray-300">
                        {pos.ticker}
                      </td>
                      <td className={`px-3 py-1.5 text-right font-semibold ${posColor}`}>
                        {pos.impact_pct > 0 ? "+" : ""}
                        {pos.impact_pct.toFixed(2)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {expanded && scenario.affected_positions.length === 0 && (
        <div className="px-4 pb-3">
          <p className="text-xs text-gray-500">
            No open positions affected by this scenario.
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export default function StressTestPanel() {
  const {
    data: scenarios,
    loading,
    error,
    refetch,
  } = useApi<StressScenario[]>(() => getStressScenarios(), {
    cacheKey: "risk:stress-test",
    ttlMs: 120_000,
  });

  if (loading) return <SkeletonCard className="h-[320px]" />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;
  if (!scenarios || scenarios.length === 0) {
    return (
      <Card>
        <CardHeader
          title="Stress Test Scenarios"
          subtitle="Impact of historical market events on your portfolio"
        />
        <CardBody>
          <p className="text-sm text-gray-500">
            No stress-test scenarios available. Add positions to see projected
            impacts.
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Stress Test Scenarios"
        subtitle="Projected portfolio impact under historical market events"
      />
      <div>
        {scenarios.map((scenario) => (
          <ScenarioRow key={scenario.name} scenario={scenario} />
        ))}
      </div>
    </Card>
  );
}
