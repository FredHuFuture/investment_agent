import { useState } from "react";
import { useApi } from "../hooks/useApi";
import {
  getSignalHistory,
  getAccuracyStats,
  getCalibration,
  getAgentPerformance,
} from "../api/endpoints";
import type {
  SignalHistoryEntry,
  AccuracyStats as AccuracyStatsType,
  CalibrationBucket,
  AgentPerformanceEntry,
} from "../api/types";
import SignalHistory from "../components/signals/SignalHistory";
import AccuracyStatsComponent from "../components/signals/AccuracyStats";
import CalibrationChart from "../components/signals/CalibrationChart";
import AgentPerformance from "../components/signals/AgentPerformance";
import { Card, CardBody } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SkeletonTable } from "../components/ui/Skeleton";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import { usePageTitle } from "../hooks/usePageTitle";

const tabs = ["History", "Accuracy", "Calibration", "Agent Perf"] as const;
type Tab = (typeof tabs)[number];

export default function SignalsPage() {
  usePageTitle("Signals");
  const [tab, setTab] = useState<Tab>("History");

  const history = useApi<SignalHistoryEntry[]>(
    () => getSignalHistory({ limit: 50 }),
  );
  const accuracy = useApi<AccuracyStatsType>(() => getAccuracyStats());
  const calibration = useApi<CalibrationBucket[]>(() => getCalibration());
  const agentPerf = useApi<Record<string, AgentPerformanceEntry>>(
    () => getAgentPerformance(),
  );

  function renderTab() {
    switch (tab) {
      case "History":
        if (history.loading) return <SkeletonTable rows={8} columns={6} />;
        if (history.error) return <ErrorAlert message={history.error} />;
        if (!history.data?.length)
          return <EmptyState message="No signal history." />;
        return <SignalHistory entries={history.data} />;

      case "Accuracy":
        if (accuracy.loading) return <SkeletonTable rows={4} columns={4} />;
        if (accuracy.error) return <ErrorAlert message={accuracy.error} />;
        if (!accuracy.data) return null;
        return <AccuracyStatsComponent data={accuracy.data} />;

      case "Calibration":
        if (calibration.loading) return <SkeletonTable rows={5} columns={3} />;
        if (calibration.error) return <ErrorAlert message={calibration.error} />;
        if (!calibration.data?.length)
          return <EmptyState message="Not enough data for calibration." />;
        return <CalibrationChart data={calibration.data} />;

      case "Agent Perf":
        if (agentPerf.loading) return <SkeletonTable rows={4} columns={5} />;
        if (agentPerf.error) return <ErrorAlert message={agentPerf.error} />;
        if (!agentPerf.data || Object.keys(agentPerf.data).length === 0)
          return <EmptyState message="No agent performance data." />;
        return (
          <AgentPerformance
            data={Object.entries(agentPerf.data).map(([name, entry]) => ({
              ...entry,
              agent: name,
            }))}
          />
        );
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Signals</h1>
      <div className="flex gap-1 border-b border-gray-800/50">
        {tabs.map((t) => (
          <Button
            key={t}
            variant={tab === t ? "primary" : "ghost"}
            size="sm"
            onClick={() => setTab(t)}
            className={`rounded-b-none border-b-2 ${
              tab === t
                ? "border-blue-500"
                : "border-transparent"
            }`}
          >
            {t}
          </Button>
        ))}
      </div>
      <Card padding="md">
        <CardBody className="p-0">
          {renderTab()}
        </CardBody>
      </Card>
    </div>
  );
}
