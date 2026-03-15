import { useState, useMemo, useCallback } from "react";
import { useApi } from "../../hooks/useApi";
import { getMonteCarloSimulation } from "../../api/endpoints";
import type { MonteCarloResult } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";
import { formatCurrency } from "../../lib/formatters";
import {
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Line,
  ComposedChart,
} from "recharts";

// ---------------------------------------------------------------------------
// Chart data transform
// ---------------------------------------------------------------------------

interface ChartPoint {
  date: string;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

function buildChartData(result: MonteCarloResult): ChartPoint[] {
  const { dates, percentiles } = result;
  const p5 = percentiles.p5 ?? [];
  const p25 = percentiles.p25 ?? [];
  const p50 = percentiles.p50 ?? [];
  const p75 = percentiles.p75 ?? [];
  const p95 = percentiles.p95 ?? [];

  return dates.map((d, i) => ({
    date: d,
    p5: p5[i] ?? 0,
    p25: p25[i] ?? 0,
    p50: p50[i] ?? 0,
    p75: p75[i] ?? 0,
    p95: p95[i] ?? 0,
  }));
}

// ---------------------------------------------------------------------------
// Tooltip formatter
// ---------------------------------------------------------------------------

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0]?.payload as ChartPoint | undefined;
  if (!point) return null;

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="text-gray-400 mb-1">{label}</p>
      <div className="space-y-0.5">
        <p className="text-blue-200">P95 (Best): {formatCurrency(point.p95)}</p>
        <p className="text-blue-300">P75: {formatCurrency(point.p75)}</p>
        <p className="text-blue-400 font-semibold">Median: {formatCurrency(point.p50)}</p>
        <p className="text-blue-300">P25: {formatCurrency(point.p25)}</p>
        <p className="text-blue-200">P5 (Worst): {formatCurrency(point.p5)}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export default function MonteCarloPanel() {
  const [horizon, setHorizon] = useState(30);
  const [simulations, setSimulations] = useState(1000);

  const fetcher = useCallback(
    () => getMonteCarloSimulation(90, simulations, horizon),
    [simulations, horizon],
  );

  const { data, loading, error, refetch } = useApi<MonteCarloResult>(
    fetcher,
    [simulations, horizon],
    { cacheKey: `risk:monte-carlo:${horizon}:${simulations}`, ttlMs: 120_000 },
  );

  const chartData = useMemo(() => {
    if (!data) return [];
    return buildChartData(data);
  }, [data]);

  // Handle error response embedded in data
  const dataError = data && "error" in data ? (data as unknown as { error: string }).error : null;

  if (loading) return <SkeletonCard className="h-[440px]" />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;

  if (dataError) {
    return (
      <Card>
        <CardHeader
          title="Monte Carlo Simulation"
          subtitle="Forward-looking probabilistic analysis"
        />
        <CardBody>
          <p className="text-sm text-gray-500">{dataError}</p>
        </CardBody>
      </Card>
    );
  }

  if (!data || chartData.length === 0) {
    return (
      <Card>
        <CardHeader
          title="Monte Carlo Simulation"
          subtitle="Forward-looking probabilistic analysis"
        />
        <CardBody>
          <p className="text-sm text-gray-500">No simulation data available.</p>
        </CardBody>
      </Card>
    );
  }

  const last = chartData[chartData.length - 1];
  const medianOutcome = last?.p50 ?? 0;
  const bestCase = last?.p95 ?? 0;
  const worstCase = last?.p5 ?? 0;
  const rangeP25 = last?.p25 ?? 0;
  const rangeP75 = last?.p75 ?? 0;

  return (
    <Card>
      <CardHeader
        title="Monte Carlo Simulation"
        subtitle="Forward-looking probabilistic analysis"
      />
      <CardBody>
        {/* Controls */}
        <div className="flex flex-wrap items-center gap-6 mb-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 whitespace-nowrap" htmlFor="mc-horizon">
              Horizon (days)
            </label>
            <input
              id="mc-horizon"
              type="range"
              min={7}
              max={90}
              step={1}
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              className="w-28 accent-blue-500"
            />
            <span className="text-xs text-gray-300 w-6 text-right">{horizon}</span>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 whitespace-nowrap" htmlFor="mc-sims">
              Simulations
            </label>
            <input
              id="mc-sims"
              type="range"
              min={100}
              max={5000}
              step={100}
              value={simulations}
              onChange={(e) => setSimulations(Number(e.target.value))}
              className="w-28 accent-blue-500"
            />
            <span className="text-xs text-gray-300 w-12 text-right">
              {simulations.toLocaleString()}
            </span>
          </div>
        </div>

        {/* Fan chart */}
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={chartData}>
            <defs>
              <linearGradient id="mcBandOuter" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.10} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="mcBandInner" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.10} />
              </linearGradient>
            </defs>

            <XAxis
              dataKey="date"
              tick={{ fill: "#6b7280", fontSize: 11 }}
              tickFormatter={formatDate}
            />
            <YAxis
              tick={{ fill: "#6b7280", fontSize: 11 }}
              tickFormatter={(v: number) => formatCurrency(v)}
              domain={["auto", "auto"]}
              width={80}
            />
            <Tooltip content={<CustomTooltip />} />

            {/* P5-P95 outer band */}
            <Area
              type="monotone"
              dataKey="p95"
              stroke="none"
              fill="url(#mcBandOuter)"
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="p5"
              stroke="none"
              fill="#111827"
              isAnimationActive={false}
            />

            {/* P25-P75 inner band */}
            <Area
              type="monotone"
              dataKey="p75"
              stroke="none"
              fill="url(#mcBandInner)"
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="p25"
              stroke="none"
              fill="#111827"
              isAnimationActive={false}
            />

            {/* Median line */}
            <Line
              type="monotone"
              dataKey="p50"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>

        {/* Stats box */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 pt-4 border-t border-gray-800/50">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">Median Outcome</p>
            <p className="text-sm font-semibold text-blue-400 mt-0.5">
              {formatCurrency(medianOutcome)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">Best Case (P95)</p>
            <p className="text-sm font-semibold text-emerald-400 mt-0.5">
              {formatCurrency(bestCase)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">Worst Case (P5)</p>
            <p className="text-sm font-semibold text-red-400 mt-0.5">
              {formatCurrency(worstCase)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">Expected Range</p>
            <p className="text-sm font-semibold text-gray-300 mt-0.5">
              {formatCurrency(rangeP25)} &ndash; {formatCurrency(rangeP75)}
            </p>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
