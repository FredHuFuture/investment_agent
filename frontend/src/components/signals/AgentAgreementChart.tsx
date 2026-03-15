import { useMemo } from "react";
import { useApi } from "../../hooks/useApi";
import { getAgentAgreement } from "../../api/endpoints";
import type { AgentAgreementEntry } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonTable } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import EmptyState from "../shared/EmptyState";

function cellColor(pct: number): string {
  if (pct > 70) return "bg-green-500/20 text-green-400";
  if (pct >= 50) return "bg-yellow-500/20 text-yellow-400";
  return "bg-red-500/20 text-red-400";
}

interface MatrixData {
  agents: string[];
  matrix: Record<string, Record<string, { pct: number; sample: number } | null>>;
}

function buildMatrix(entries: AgentAgreementEntry[]): MatrixData {
  const agentSet = new Set<string>();
  for (const e of entries) {
    agentSet.add(e.agent_a);
    agentSet.add(e.agent_b);
  }
  const agents = Array.from(agentSet).sort();

  const matrix: MatrixData["matrix"] = {};
  for (const a of agents) {
    const row: Record<string, { pct: number; sample: number } | null> = {};
    for (const b of agents) {
      row[b] = a === b ? { pct: 100, sample: 0 } : null;
    }
    matrix[a] = row;
  }

  for (const e of entries) {
    const cell = { pct: e.agreement_pct, sample: e.sample_size };
    const rowA = matrix[e.agent_a];
    const rowB = matrix[e.agent_b];
    if (rowA) rowA[e.agent_b] = cell;
    if (rowB) rowB[e.agent_a] = cell;
  }

  return { agents, matrix };
}

export default function AgentAgreementChart() {
  const { data, loading, error, refetch } = useApi<AgentAgreementEntry[]>(
    () => getAgentAgreement(),
    [],
    { cacheKey: "signals:agent-agreement", ttlMs: 60_000 },
  );

  const matrixData = useMemo(() => {
    if (!data || data.length === 0) return null;
    return buildMatrix(data);
  }, [data]);

  return (
    <Card>
      <CardHeader title="Agent Agreement Matrix" subtitle="Pairwise signal direction agreement rates" />
      <CardBody>
        {loading && <SkeletonTable rows={4} columns={4} />}
        {error && <ErrorAlert message={error} onRetry={refetch} />}
        {!loading && !error && !matrixData && (
          <EmptyState
            message="No agent agreement data available."
            hint="Agreement data requires signals with multiple agents."
          />
        )}
        {!loading && !error && matrixData && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="px-3 py-2 text-left text-gray-500 font-medium" />
                  {matrixData.agents.map((agent) => (
                    <th
                      key={agent}
                      className="px-3 py-2 text-center text-gray-400 font-medium whitespace-nowrap"
                    >
                      {agent}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrixData.agents.map((rowAgent) => (
                  <tr key={rowAgent} className="border-t border-gray-800/30">
                    <td className="px-3 py-2 text-gray-400 font-medium whitespace-nowrap">
                      {rowAgent}
                    </td>
                    {matrixData.agents.map((colAgent) => {
                      const cell = matrixData.matrix[rowAgent]?.[colAgent];
                      const isDiag = rowAgent === colAgent;
                      return (
                        <td key={colAgent} className="px-3 py-2 text-center">
                          {isDiag ? (
                            <span className="text-gray-600 font-mono">--</span>
                          ) : cell ? (
                            <span
                              className={`inline-block px-2 py-0.5 rounded font-mono font-semibold ${cellColor(cell.pct)}`}
                              title={`${cell.sample} signals compared`}
                            >
                              {cell.pct.toFixed(0)}%
                            </span>
                          ) : (
                            <span className="text-gray-700">--</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Legend */}
            <div className="mt-4 flex items-center gap-4 text-[10px] text-gray-500 px-1">
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded bg-green-500/20" />
                &gt;70%
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded bg-yellow-500/20" />
                50-70%
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded bg-red-500/20" />
                &lt;50%
              </span>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
