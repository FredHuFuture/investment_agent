import { useMemo } from "react";
import { useApi } from "../../hooks/useApi";
import { getSignalHistory, getAccuracyStats } from "../../api/endpoints";
import type { SignalHistoryEntry, AccuracyStats } from "../../api/types";
import { Card, CardHeader, CardBody } from "../../components/ui/Card";
import { SkeletonCard } from "../../components/ui/Skeleton";

export default function SignalSummaryCard() {
  const signalApi = useApi<SignalHistoryEntry[]>(
    () => getSignalHistory({ limit: 50 }),
    { cacheKey: "dashboard:signalSummary", ttlMs: 60_000 },
  );
  const accuracyApi = useApi<AccuracyStats>(
    () => getAccuracyStats(),
    { cacheKey: "dashboard:accuracyStats", ttlMs: 60_000 },
  );

  const counts = useMemo(() => {
    if (!signalApi.data) return { buy: 0, hold: 0, sell: 0, total: 0 };
    let buy = 0;
    let hold = 0;
    let sell = 0;
    for (const entry of signalApi.data) {
      const sig = entry.final_signal.toUpperCase();
      if (sig === "BUY") buy++;
      else if (sig === "SELL") sell++;
      else hold++;
    }
    return { buy, hold, sell, total: buy + hold + sell };
  }, [signalApi.data]);

  if (signalApi.loading && !signalApi.data) {
    return <SkeletonCard />;
  }

  const buyPct = counts.total > 0 ? (counts.buy / counts.total) * 100 : 0;
  const holdPct = counts.total > 0 ? (counts.hold / counts.total) * 100 : 0;
  const sellPct = counts.total > 0 ? (counts.sell / counts.total) * 100 : 0;

  const accuracy =
    accuracyApi.data?.win_rate != null
      ? `${(accuracyApi.data.win_rate * 100).toFixed(1)}%`
      : "--";

  return (
    <Card>
      <CardHeader title="Signal Summary" />
      <CardBody>
        {/* Stacked bar */}
        <div className="flex h-5 w-full rounded overflow-hidden">
          {buyPct > 0 && (
            <div
              className="bg-emerald-500"
              style={{ width: `${buyPct}%` }}
              title={`BUY: ${counts.buy}`}
            />
          )}
          {holdPct > 0 && (
            <div
              className="bg-gray-500"
              style={{ width: `${holdPct}%` }}
              title={`HOLD: ${counts.hold}`}
            />
          )}
          {sellPct > 0 && (
            <div
              className="bg-red-500"
              style={{ width: `${sellPct}%` }}
              title={`SELL: ${counts.sell}`}
            />
          )}
        </div>

        {/* Counts */}
        <div className="flex justify-between mt-3 text-xs">
          <span className="text-emerald-400">
            BUY <span className="font-medium">{counts.buy}</span>
          </span>
          <span className="text-gray-400">
            HOLD <span className="font-medium">{counts.hold}</span>
          </span>
          <span className="text-red-400">
            SELL <span className="font-medium">{counts.sell}</span>
          </span>
        </div>

        {/* Accuracy */}
        <div className="mt-4 pt-3 border-t border-gray-800/50">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Overall Accuracy</span>
            <span className="font-medium text-white">{accuracy}</span>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
