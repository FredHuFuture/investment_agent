import MetricCard from "../shared/MetricCard";
import type { AccuracyStats as AccuracyStatsType } from "../../api/types";

export default function AccuracyStats({ data }: { data: AccuracyStatsType }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Total Signals" value={String(data.total_signals)} />
        <MetricCard label="Resolved" value={String(data.resolved_count)} />
        <MetricCard label="Wins" value={String(data.win_count)} />
        <MetricCard
          label="Win Rate"
          value={data.win_rate != null ? `${data.win_rate.toFixed(1)}%` : "N/A"}
        />
      </div>
      {Object.keys(data.by_signal).length > 0 && (
        <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
          <h3 className="text-sm font-semibold text-gray-400 mb-2">
            By Signal
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(data.by_signal).map(([signal, stats]) => (
              <div key={signal} className="text-sm">
                <span className="font-semibold">{signal}</span>
                <span className="text-gray-400 ml-2">
                  {stats.count} signals
                  {stats.win_rate != null
                    ? ` (${stats.win_rate.toFixed(1)}%)`
                    : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {Object.keys(data.by_regime).length > 0 && (
        <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
          <h3 className="text-sm font-semibold text-gray-400 mb-2">
            By Regime
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(data.by_regime).map(([regime, stats]) => (
              <div key={regime} className="text-sm">
                <span className="font-semibold">{regime}</span>
                <span className="text-gray-400 ml-2">
                  {stats.count} signals
                  {stats.win_rate != null
                    ? ` (${stats.win_rate.toFixed(1)}%)`
                    : ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
