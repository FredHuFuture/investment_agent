import { useMemo } from "react";
import { useApi } from "../hooks/useApi";
import {
  getPortfolioRisk,
  getPortfolioCorrelations,
  getValueHistory,
} from "../api/endpoints";
import type {
  PortfolioRisk,
  CorrelationData,
  ValueHistoryPoint,
} from "../api/types";
import MetricCard from "../components/shared/MetricCard";
import ErrorAlert from "../components/shared/ErrorAlert";
import StressTestPanel from "../components/risk/StressTestPanel";
import MonteCarloPanel from "../components/risk/MonteCarloPanel";
import CorrelationHeatmap from "../components/risk/CorrelationHeatmap";
import HealthScoreCard from "../components/risk/HealthScoreCard";
import { Card, CardHeader, CardBody } from "../components/ui/Card";
import { SkeletonCard } from "../components/ui/Skeleton";
import { usePageTitle } from "../hooks/usePageTitle";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pct(value: number): string {
  return (value * 100).toFixed(1) + "%";
}

function pct2(value: number): string {
  return (value * 100).toFixed(2) + "%";
}

// ---------------------------------------------------------------------------
// Risk status helpers
// ---------------------------------------------------------------------------

type RiskLevel = "red" | "amber" | "green";

interface RiskStatus {
  level: RiskLevel;
  message: string;
}

function computeRiskStatus(risk: PortfolioRisk): RiskStatus {
  if (risk.current_drawdown_pct < -0.10) {
    return {
      level: "red",
      message: `Portfolio in significant drawdown (${pct(risk.current_drawdown_pct)})`,
    };
  }
  if (risk.current_drawdown_pct < -0.05) {
    return {
      level: "amber",
      message: `Portfolio in moderate drawdown (${pct(risk.current_drawdown_pct)})`,
    };
  }
  if (risk.annualized_volatility > 0.30) {
    return {
      level: "amber",
      message: `High volatility detected (${pct(risk.annualized_volatility)})`,
    };
  }
  if (risk.sharpe_ratio !== null && risk.sharpe_ratio < 0.5) {
    return {
      level: "amber",
      message: `Low risk-adjusted returns (Sharpe: ${risk.sharpe_ratio.toFixed(2)})`,
    };
  }
  return {
    level: "green",
    message: "Portfolio risk metrics within normal range",
  };
}

const riskBannerStyles: Record<RiskLevel, string> = {
  red: "bg-red-400/10 border-red-400/30 text-red-300",
  amber: "bg-amber-400/10 border-amber-400/30 text-amber-300",
  green: "bg-emerald-400/10 border-emerald-400/30 text-emerald-300",
};

function computeRiskBadge(maxDrawdown: number): { label: string; style: string } {
  // maxDrawdown is negative (e.g. -0.15 for 15% drawdown)
  const absDd = Math.abs(maxDrawdown);
  if (absDd > 0.20) {
    return { label: "HIGH RISK", style: "bg-red-400/20 text-red-400" };
  }
  if (absDd > 0.10) {
    return { label: "MODERATE", style: "bg-amber-400/20 text-amber-400" };
  }
  return { label: "LOW RISK", style: "bg-green-400/20 text-green-400" };
}

function concentrationBadgeColor(risk: CorrelationData["concentration_risk"]): string {
  if (risk === "HIGH") return "bg-red-500/20 text-red-400 border border-red-500/30";
  if (risk === "MODERATE") return "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30";
  return "bg-green-500/20 text-green-400 border border-green-500/30";
}

function correlationCellStyle(value: number): string {
  if (value >= 0.7) return "bg-red-500/25 text-red-300";
  if (value >= 0.3) return "bg-yellow-500/20 text-yellow-300";
  return "bg-green-500/15 text-green-300";
}

// ---------------------------------------------------------------------------
// Correlation Matrix sub-component
// ---------------------------------------------------------------------------

function CorrelationMatrix({ data }: { data: CorrelationData }) {
  const { tickers, correlation_matrix, concentration_risk, high_correlation_pairs } = data;

  function getCorr(t1: string, t2: string): number | null {
    const key1 = `${t1}:${t2}`;
    const key2 = `${t2}:${t1}`;
    if (correlation_matrix[key1] !== undefined) return correlation_matrix[key1];
    if (correlation_matrix[key2] !== undefined) return correlation_matrix[key2];
    return null;
  }

  return (
    <div className="space-y-4">
      {/* Concentration risk badge */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-500 uppercase tracking-wider">Concentration Risk</span>
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${concentrationBadgeColor(concentration_risk)}`}
        >
          {concentration_risk}
        </span>
        <span className="text-xs text-gray-500">
          Avg correlation: {(data.avg_correlation * 100).toFixed(1)}%
        </span>
      </div>

      {/* Matrix table */}
      {tickers.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="text-xs border-collapse">
            <thead>
              <tr>
                <th className="w-16 pr-2 text-right text-gray-600" />
                {tickers.map((t) => (
                  <th
                    key={t}
                    className="px-2 py-1 text-center font-mono font-medium text-gray-400 min-w-[56px]"
                  >
                    {t}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tickers.map((rowTicker) => (
                <tr key={rowTicker}>
                  <td className="pr-2 py-1 text-right font-mono font-medium text-gray-400 whitespace-nowrap">
                    {rowTicker}
                  </td>
                  {tickers.map((colTicker) => {
                    if (rowTicker === colTicker) {
                      return (
                        <td
                          key={colTicker}
                          className="px-2 py-1 text-center text-gray-600 bg-gray-800/30 rounded"
                        >
                          1.00
                        </td>
                      );
                    }
                    const val = getCorr(rowTicker, colTicker);
                    return (
                      <td
                        key={colTicker}
                        className={`px-2 py-1 text-center rounded ${val !== null ? correlationCellStyle(Math.abs(val)) : "text-gray-700"}`}
                      >
                        {val !== null ? val.toFixed(2) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-gray-500">No tickers with sufficient data.</p>
      )}

      {/* High correlation warnings */}
      {high_correlation_pairs.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs text-gray-500 uppercase tracking-wider">High Correlation Pairs</p>
          {high_correlation_pairs.map(([t1, t2, corr]) => (
            <div
              key={`${t1}-${t2}`}
              className="flex items-center gap-2 text-xs text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2"
            >
              <svg
                className="w-3.5 h-3.5 shrink-0"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <path d="M12 9v4" />
                <path d="M12 17h.01" />
              </svg>
              <span>
                <span className="font-mono font-semibold">{t1}</span>
                {" & "}
                <span className="font-mono font-semibold">{t2}</span>
                {" — correlation: "}
                <span className="font-semibold">{(corr * 100).toFixed(1)}%</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Win/Loss Distribution sub-component
// ---------------------------------------------------------------------------

function WinLossDistribution({
  positivedays,
  negativeDays,
  sortinoRatio,
}: {
  positivedays: number;
  negativeDays: number;
  sortinoRatio: number | null;
}) {
  const total = positivedays + negativeDays;
  const winPct = total > 0 ? (positivedays / total) * 100 : 0;
  const lossPct = total > 0 ? (negativeDays / total) * 100 : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <span className="text-green-400 font-semibold">{positivedays}</span>
          <span className="text-gray-500">positive days</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-gray-500">negative days</span>
          <span className="text-red-400 font-semibold">{negativeDays}</span>
        </div>
      </div>

      {/* Bar */}
      <div className="w-full h-5 rounded-full overflow-hidden bg-gray-800 flex">
        {winPct > 0 && (
          <div
            className="bg-green-500/70 h-full transition-all duration-500"
            style={{ width: `${winPct}%` }}
          />
        )}
        {lossPct > 0 && (
          <div
            className="bg-red-500/70 h-full transition-all duration-500"
            style={{ width: `${lossPct}%` }}
          />
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{winPct.toFixed(1)}% positive</span>
        <span>{total} total trading days</span>
        <span>{lossPct.toFixed(1)}% negative</span>
      </div>

      {sortinoRatio !== null && (
        <div className="pt-2 border-t border-gray-800/50">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500 uppercase tracking-wider">Sortino Ratio</span>
            <span
              className={`text-sm font-bold ${sortinoRatio >= 1.0 ? "text-green-400" : sortinoRatio >= 0 ? "text-yellow-400" : "text-red-400"}`}
            >
              {sortinoRatio.toFixed(2)}
            </span>
          </div>
          <p className="text-xs text-gray-600 mt-1">
            Risk-adjusted return relative to downside deviation
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function RiskPage() {
  usePageTitle("Risk");

  const riskApi = useApi<PortfolioRisk>(
    () => getPortfolioRisk(90),
    { cacheKey: "risk:metrics", ttlMs: 60_000 },
  );
  const corrApi = useApi<CorrelationData>(
    () => getPortfolioCorrelations(90),
    { cacheKey: "risk:correlations", ttlMs: 120_000 },
  );
  const valueApi = useApi<ValueHistoryPoint[]>(
    () => getValueHistory(90),
    { cacheKey: "risk:value-history", ttlMs: 60_000 },
  );

  // Compute drawdown series from value history
  const drawdownData = useMemo(() => {
    if (!valueApi.data || valueApi.data.length < 2) return [];
    const first = valueApi.data[0];
    if (!first) return [];
    let peak = first.total_value;
    return valueApi.data.map((pt) => {
      if (pt.total_value > peak) peak = pt.total_value;
      const dd = peak > 0 ? ((pt.total_value - peak) / peak) * 100 : 0;
      return { date: pt.date.slice(0, 10), drawdown: parseFloat(dd.toFixed(2)) };
    });
  }, [valueApi.data]);

  const loading = riskApi.loading || corrApi.loading || valueApi.loading;
  const error = riskApi.error || corrApi.error || valueApi.error;

  function refetchAll() {
    riskApi.refetch();
    corrApi.refetch();
    valueApi.refetch();
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Risk Dashboard</h1>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }, (_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <SkeletonCard className="h-[260px]" />
          <SkeletonCard className="h-[260px]" />
        </div>
        <SkeletonCard className="h-[300px]" />
        <SkeletonCard className="h-[260px]" />
      </div>
    );
  }

  if (error) return <ErrorAlert message={error} onRetry={refetchAll} />;

  const risk = riskApi.data;
  const riskStatus = risk ? computeRiskStatus(risk) : null;
  const riskBadge = risk ? computeRiskBadge(risk.max_drawdown_pct) : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold text-white">Risk Dashboard</h1>
        {riskBadge && (
          <span
            className={`inline-block rounded-full px-3 py-1 text-xs font-medium ${riskBadge.style}`}
          >
            {riskBadge.label}
          </span>
        )}
      </div>

      {/* Risk status banner */}
      {riskStatus && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${riskBannerStyles[riskStatus.level]}`}
        >
          <div className="flex items-center gap-2">
            <span className="shrink-0">
              {riskStatus.level === "red"
                ? "\u26A0\uFE0F"
                : riskStatus.level === "amber"
                  ? "\u26A0"
                  : "\u2714\uFE0F"}
            </span>
            <span>{riskStatus.message}</span>
          </div>
        </div>
      )}

      {/* Row 1: Core volatility & drawdown metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Annualized Volatility"
          value={risk ? pct(risk.annualized_volatility) : "—"}
          sub={risk ? `Daily: ${pct(risk.daily_volatility)}` : undefined}
          trend="down"
        />
        <MetricCard
          label="Sharpe Ratio"
          value={risk?.sharpe_ratio != null ? risk.sharpe_ratio.toFixed(2) : "—"}
          sub="Risk-adjusted return"
          trend={
            risk?.sharpe_ratio != null
              ? risk.sharpe_ratio >= 1.0
                ? "up"
                : "down"
              : undefined
          }
        />
        <MetricCard
          label="Max Drawdown"
          value={risk ? pct(risk.max_drawdown_pct) : "—"}
          sub="Peak-to-trough"
          trend="down"
        />
        <MetricCard
          label="Current Drawdown"
          value={risk ? pct(risk.current_drawdown_pct) : "—"}
          sub="From recent peak"
          trend={
            risk
              ? risk.current_drawdown_pct < 0
                ? "down"
                : undefined
              : undefined
          }
        />
      </div>

      {/* Row 2: Tail risk & daily extremes */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="VaR (95%)"
          value={risk ? pct2(risk.var_95) : "—"}
          sub="1-day value at risk"
          trend="down"
        />
        <MetricCard
          label="CVaR (95%)"
          value={risk ? pct2(risk.cvar_95) : "—"}
          sub="Expected shortfall"
          trend="down"
        />
        <MetricCard
          label="Best Day"
          value={risk ? `+${pct2(risk.best_day_pct)}` : "—"}
          sub={risk ? `${risk.data_points} data points` : undefined}
          trend="up"
        />
        <MetricCard
          label="Worst Day"
          value={risk ? pct2(risk.worst_day_pct) : "—"}
          trend="down"
        />
      </div>

      {/* Portfolio Health Score */}
      <HealthScoreCard />

      {/* Row 3: Win/Loss distribution + Correlation matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Win/Loss day distribution */}
        <Card>
          <CardHeader title="Win / Loss Day Distribution" />
          <CardBody>
            {risk ? (
              <WinLossDistribution
                positivedays={risk.positive_days}
                negativeDays={risk.negative_days}
                sortinoRatio={risk.sortino_ratio}
              />
            ) : (
              <p className="text-sm text-gray-500">No risk data available.</p>
            )}
          </CardBody>
        </Card>

        {/* Correlation matrix */}
        <Card>
          <CardHeader title="Correlation Matrix" />
          <CardBody>
            {corrApi.data ? (
              <CorrelationMatrix data={corrApi.data} />
            ) : (
              <p className="text-sm text-gray-500">
                No correlation data available. Portfolio requires at least 2 positions with
                sufficient price history.
              </p>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Drawdown chart */}
      <Card>
        <CardHeader
          title="Drawdown (90 days)"
          subtitle="Percentage decline from rolling peak portfolio value"
        />
        <CardBody>
          {drawdownData.length < 2 ? (
            <div className="flex items-center justify-center h-[220px] text-sm text-gray-500">
              Insufficient value history to compute drawdown.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={drawdownData}>
                <defs>
                  <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  tickFormatter={(v) => {
                    const d = new Date(v);
                    return `${d.getMonth() + 1}/${d.getDate()}`;
                  }}
                />
                <YAxis
                  tick={{ fill: "#6b7280", fontSize: 11 }}
                  tickFormatter={(v) => `${v.toFixed(1)}%`}
                  domain={["auto", 0]}
                />
                <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#111827",
                    border: "1px solid #374151",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value: number) => [`${value.toFixed(2)}%`, "Drawdown"]}
                  labelFormatter={(v) => String(v)}
                />
                <Area
                  type="monotone"
                  dataKey="drawdown"
                  stroke="#ef4444"
                  fill="url(#ddGradient)"
                  strokeWidth={2}
                  name="Drawdown"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardBody>
      </Card>

      {/* Stress Test Scenarios */}
      <StressTestPanel />

      {/* Monte Carlo Simulation */}
      <MonteCarloPanel />

      {/* Correlation Heatmap */}
      <CorrelationHeatmap />
    </div>
  );
}
