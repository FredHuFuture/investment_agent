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
import LoadingSpinner from "../components/shared/LoadingSpinner";
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
        if (history.loading) return <LoadingSpinner />;
        if (history.error) return <ErrorAlert message={history.error} />;
        if (!history.data?.length)
          return <EmptyState message="No signal history." />;
        return <SignalHistory entries={history.data} />;

      case "Accuracy":
        if (accuracy.loading) return <LoadingSpinner />;
        if (accuracy.error) return <ErrorAlert message={accuracy.error} />;
        if (!accuracy.data) return null;
        return <AccuracyStatsComponent data={accuracy.data} />;

      case "Calibration":
        if (calibration.loading) return <LoadingSpinner />;
        if (calibration.error) return <ErrorAlert message={calibration.error} />;
        if (!calibration.data?.length)
          return <EmptyState message="Not enough data for calibration." />;
        return <CalibrationChart data={calibration.data} />;

      case "Agent Perf":
        if (agentPerf.loading) return <LoadingSpinner />;
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
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-blue-500 text-white"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      {renderTab()}
    </div>
  );
}
