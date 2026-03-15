import { useEffect, useMemo, useState } from "react";
import { useApi } from "../hooks/useApi";
import { getPositionHistory, getPerformanceSummary, getTradeAnnotations } from "../api/endpoints";
import type { Position, PerformanceSummary, TradeAnnotation } from "../api/types";
import { Card, CardHeader, CardBody } from "../components/ui/Card";
import { SkeletonTable, SkeletonCard } from "../components/ui/Skeleton";
import MetricCard from "../components/shared/MetricCard";
import ErrorAlert from "../components/shared/ErrorAlert";
import EmptyState from "../components/shared/EmptyState";
import WarningsBanner from "../components/shared/WarningsBanner";
import { formatCurrency, formatDate, pnlColor } from "../lib/formatters";
import { usePageTitle } from "../hooks/usePageTitle";
import DataTable, { type Column } from "../components/shared/DataTable";
import TradeAnnotationPanel from "../components/journal/TradeAnnotationPanel";
import LessonSummary from "../components/journal/LessonSummary";
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  Cell,
} from "recharts";

function returnPct(pos: Position): number {
  if (
    pos.realized_pnl != null &&
    pos.cost_basis > 0
  ) {
    return (pos.realized_pnl / pos.cost_basis) * 100;
  }
  return 0;
}

// ---------------------------------------------------------------------------
// Column definitions (defined outside component to avoid recreation on render)
// ---------------------------------------------------------------------------
const journalColumns: Column<Position>[] = [
  {
    key: "ticker",
    header: "Ticker",
    render: (r) => <span className="font-mono text-white font-medium">{r.ticker}</span>,
    sortValue: (r) => r.ticker,
    searchValue: (r) => r.ticker,
  },
  {
    key: "entry",
    header: "Entry",
    render: (r) => <span className="text-gray-400">{formatDate(r.entry_date)}</span>,
    sortValue: (r) => r.entry_date,
    hiddenOnMobile: true,
  },
  {
    key: "exit",
    header: "Exit",
    render: (r) => <span className="text-gray-400">{r.exit_date ? formatDate(r.exit_date) : "--"}</span>,
    sortValue: (r) => r.exit_date ?? "",
  },
  {
    key: "entry_price",
    header: "Entry $",
    render: (r) => <span className="text-gray-300 font-mono">{formatCurrency(r.avg_cost)}</span>,
    sortValue: (r) => r.avg_cost,
    hiddenOnMobile: true,
  },
  {
    key: "exit_price",
    header: "Exit $",
    render: (r) => <span className="text-gray-300 font-mono">{r.exit_price != null ? formatCurrency(r.exit_price) : "--"}</span>,
    sortValue: (r) => r.exit_price ?? 0,
    hiddenOnMobile: true,
  },
  {
    key: "return",
    header: "Return",
    render: (r) => {
      const ret = returnPct(r);
      return <span className={`font-mono font-medium ${pnlColor(ret)}`}>{ret >= 0 ? "+" : ""}{ret.toFixed(1)}%</span>;
    },
    sortValue: (r) => returnPct(r),
  },
  {
    key: "pnl",
    header: "P&L",
    render: (r) => {
      const pnl = r.realized_pnl ?? 0;
      return <span className={`font-mono ${pnlColor(pnl)}`}>{pnl >= 0 ? "+" : ""}{formatCurrency(pnl)}</span>;
    },
    sortValue: (r) => r.realized_pnl ?? 0,
  },
  {
    key: "reason",
    header: "Reason",
    render: (r) => <span className="text-gray-400 text-xs">{r.exit_reason ? r.exit_reason.replace(/_/g, " ") : "--"}</span>,
    searchValue: (r) => r.exit_reason ?? "",
    hiddenOnMobile: true,
  },
  {
    key: "days",
    header: "Days",
    render: (r) => <span className="text-gray-400 font-mono">{r.holding_days}</span>,
    sortValue: (r) => r.holding_days,
    hiddenOnMobile: true,
  },
  {
    key: "thesis",
    header: "Thesis",
    render: (r) => (
      <span className="text-gray-500 text-xs max-w-[200px] truncate block">{r.thesis_text || "--"}</span>
    ),
    searchValue: (r) => r.thesis_text ?? "",
    hiddenOnMobile: true,
  },
];

// ---------------------------------------------------------------------------
// Expandable row detail
// ---------------------------------------------------------------------------
function TradeDetail({ pos }: { pos: Position }) {
  const actual = returnPct(pos);
  const expectedPct =
    pos.expected_return_pct != null ? pos.expected_return_pct * 100 : null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
      {/* Thesis */}
      <div>
        <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
          Thesis
        </div>
        <p className="text-gray-300 leading-relaxed">
          {pos.thesis_text || "No thesis recorded."}
        </p>
      </div>

      {/* Expected vs Actual Return */}
      <div>
        <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
          Return: Expected vs Actual
        </div>
        <div className="space-y-1">
          <div className="flex justify-between">
            <span className="text-gray-500">Expected</span>
            <span className="text-gray-300 font-mono">
              {expectedPct != null ? `${expectedPct.toFixed(1)}%` : "--"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Actual</span>
            <span className={`font-mono font-medium ${pnlColor(actual)}`}>
              {actual >= 0 ? "+" : ""}
              {actual.toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      {/* Hold Days & Targets */}
      <div>
        <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
          Hold Days: Expected vs Actual
        </div>
        <div className="space-y-1">
          <div className="flex justify-between">
            <span className="text-gray-500">Expected</span>
            <span className="text-gray-300 font-mono">
              {pos.expected_hold_days != null
                ? `${pos.expected_hold_days}d`
                : "--"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Actual</span>
            <span className="text-gray-300 font-mono">
              {pos.holding_days}d
            </span>
          </div>
          {pos.target_price != null && (
            <div className="flex justify-between mt-1">
              <span className="text-gray-500">Target</span>
              <span className="text-gray-300 font-mono">
                {formatCurrency(pos.target_price)}
              </span>
            </div>
          )}
          {pos.stop_loss != null && (
            <div className="flex justify-between">
              <span className="text-gray-500">Stop Loss</span>
              <span className="text-gray-300 font-mono">
                {formatCurrency(pos.stop_loss)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function JournalPage() {
  usePageTitle("Trade Journal");

  const historyApi = useApi<Position[]>(() => getPositionHistory(), {
    cacheKey: "journal:history",
    ttlMs: 60_000,
  });

  const summaryApi = useApi<PerformanceSummary>(
    () => getPerformanceSummary(),
    { cacheKey: "journal:summary", ttlMs: 60_000 },
  );

  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [allAnnotations, setAllAnnotations] = useState<TradeAnnotation[]>([]);

  // Fetch annotations for all closed tickers (for LessonSummary)
  useEffect(() => {
    if (!historyApi.data || historyApi.data.length === 0) return;
    const tickers = [...new Set(historyApi.data.map((p) => p.ticker))];
    let cancelled = false;

    Promise.all(tickers.map((t) => getTradeAnnotations(t).catch(() => ({ data: [] as TradeAnnotation[], warnings: [] as string[] }))))
      .then((results) => {
        if (cancelled) return;
        const flat = results.flatMap((r) => r.data);
        setAllAnnotations(flat);
      });

    return () => { cancelled = true; };
  }, [historyApi.data]);

  // Sort closed positions by exit_date DESC
  const closedPositions = useMemo(() => {
    if (!historyApi.data) return [];
    return [...historyApi.data].sort((a, b) => {
      const da = a.exit_date ?? "";
      const db = b.exit_date ?? "";
      return db.localeCompare(da);
    });
  }, [historyApi.data]);

  // Return distribution histogram data
  const distributionData = useMemo(() => {
    if (closedPositions.length === 0) return [];
    const bins = [
      { label: "< -20%", min: -Infinity, max: -20, count: 0 },
      { label: "-20 to -10%", min: -20, max: -10, count: 0 },
      { label: "-10 to -5%", min: -10, max: -5, count: 0 },
      { label: "-5 to 0%", min: -5, max: 0, count: 0 },
      { label: "0 to 5%", min: 0, max: 5, count: 0 },
      { label: "5 to 10%", min: 5, max: 10, count: 0 },
      { label: "10 to 20%", min: 10, max: 20, count: 0 },
      { label: "> 20%", min: 20, max: Infinity, count: 0 },
    ];
    for (const pos of closedPositions) {
      const ret = returnPct(pos);
      for (const bin of bins) {
        if (ret >= bin.min && ret < bin.max) {
          bin.count++;
          break;
        }
      }
    }
    return bins.map((b) => ({
      bin: b.label,
      count: b.count,
      negative: b.max <= 0,
    }));
  }, [closedPositions]);

  // Cumulative equity curve data
  const equityCurveData = useMemo(() => {
    if (closedPositions.length === 0) return [];
    const sortedByExitDate = [...closedPositions].sort((a, b) => {
      const da = a.exit_date ?? "";
      const db = b.exit_date ?? "";
      return da.localeCompare(db);
    });
    let cumulative = 0;
    return sortedByExitDate.map((pos) => {
      cumulative += pos.realized_pnl ?? 0;
      return { date: pos.exit_date ?? "", equity: cumulative };
    });
  }, [closedPositions]);

  const loading = historyApi.loading || summaryApi.loading;
  const error = historyApi.error || summaryApi.error;
  const warnings = [...historyApi.warnings, ...summaryApi.warnings];
  const perf = summaryApi.data;

  if (error) return <ErrorAlert message={error} onRetry={() => { historyApi.refetch(); summaryApi.refetch(); }} />;

  const pnlTrend =
    perf && perf.total_realized_pnl >= 0 ? "up" : "down";
  const pnlSign = perf && perf.total_realized_pnl >= 0 ? "+" : "";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Trade Journal</h1>
      <WarningsBanner warnings={warnings} />

      {/* Loading skeleton */}
      {loading && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }, (_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
          <SkeletonTable rows={8} columns={8} />
        </>
      )}

      {/* Summary stats */}
      {!loading && perf && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <MetricCard
              label="Total Trades"
              value={String(perf.total_trades)}
              sub={`${perf.win_count}W / ${perf.loss_count}L`}
            />
            <MetricCard
              label="Win Rate"
              value={`${perf.win_rate.toFixed(1)}%`}
              sub={`Avg win +${perf.avg_win_pct.toFixed(1)}% / loss ${perf.avg_loss_pct.toFixed(1)}%`}
              trend={perf.win_rate >= 50 ? "up" : perf.win_rate > 0 ? "down" : undefined}
            />
            <MetricCard
              label="Avg Hold Days"
              value={`${perf.avg_hold_days.toFixed(0)}d`}
            />
            <MetricCard
              label="Total Realized P&L"
              value={`${pnlSign}${formatCurrency(perf.total_realized_pnl)}`}
              trend={pnlTrend}
            />
          </div>

          {/* Best / Worst Trade */}
          {(perf.best_trade || perf.worst_trade) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {perf.best_trade && (
                <Card>
                  <CardHeader title="Best Trade" />
                  <CardBody>
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-mono font-bold text-white">
                        {perf.best_trade.ticker}
                      </span>
                      <div className="text-right">
                        <div className="text-emerald-400 font-mono font-semibold">
                          +{perf.best_trade.return_pct.toFixed(1)}%
                        </div>
                        <div className="text-emerald-400/70 text-sm">
                          +{formatCurrency(perf.best_trade.pnl)}
                        </div>
                      </div>
                    </div>
                  </CardBody>
                </Card>
              )}
              {perf.worst_trade && (
                <Card>
                  <CardHeader title="Worst Trade" />
                  <CardBody>
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-mono font-bold text-white">
                        {perf.worst_trade.ticker}
                      </span>
                      <div className="text-right">
                        <div className="text-red-400 font-mono font-semibold">
                          {perf.worst_trade.return_pct.toFixed(1)}%
                        </div>
                        <div className="text-red-400/70 text-sm">
                          {formatCurrency(perf.worst_trade.pnl)}
                        </div>
                      </div>
                    </div>
                  </CardBody>
                </Card>
              )}
            </div>
          )}

          {/* Return Distribution & Cumulative P&L Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Return Distribution Histogram */}
            <Card>
              <CardHeader title="Return Distribution" />
              <CardBody>
                {distributionData.length === 0 ? (
                  <EmptyState message="No closed trades yet." />
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={distributionData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis
                        dataKey="bin"
                        tick={{ fill: "#6b7280", fontSize: 10 }}
                        interval={0}
                        angle={-30}
                        textAnchor="end"
                        height={50}
                      />
                      <YAxis
                        tick={{ fill: "#6b7280", fontSize: 11 }}
                        allowDecimals={false}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#111827",
                          border: "1px solid #374151",
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                        formatter={(value: number) => [value, "Trades"]}
                      />
                      <Bar dataKey="count" radius={[4, 4, 0, 0]} name="Trades">
                        {distributionData.map((entry, index) => (
                          <Cell
                            key={`dist-${index}`}
                            fill={entry.negative ? "#ef4444" : "#10b981"}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardBody>
            </Card>

            {/* Cumulative Equity Curve */}
            <Card>
              <CardHeader title="Cumulative P&L" />
              <CardBody>
                {equityCurveData.length === 0 ? (
                  <EmptyState message="No closed trades yet." />
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={equityCurveData}>
                      <defs>
                        <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: "#6b7280", fontSize: 11 }}
                        tickFormatter={(v: string) => {
                          const d = new Date(v);
                          return `${d.getMonth() + 1}/${d.getDate()}`;
                        }}
                      />
                      <YAxis
                        tick={{ fill: "#6b7280", fontSize: 11 }}
                        tickFormatter={(v: number) => formatCurrency(v)}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#111827",
                          border: "1px solid #374151",
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                        labelFormatter={(v: string) => formatDate(v)}
                        formatter={(value: number) => [formatCurrency(value), "Cumulative P&L"]}
                      />
                      <ReferenceLine y={0} stroke="#4b5563" strokeDasharray="3 3" />
                      <Area
                        type="monotone"
                        dataKey="equity"
                        stroke="#10b981"
                        fill="url(#colorEquity)"
                        strokeWidth={2}
                        name="Cumulative P&L"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </CardBody>
            </Card>
          </div>
        </>
      )}

      {/* Lesson Summary */}
      {!loading && closedPositions.length > 0 && (
        <LessonSummary annotations={allAnnotations} />
      )}

      {/* Closed Positions Table */}
      {!loading && (
        <Card>
          <CardHeader
            title="Closed Positions"
            subtitle={`${closedPositions.length} trades`}
          />
          <CardBody className="p-0">
            {closedPositions.length === 0 ? (
              <div className="p-5">
                <EmptyState message="No closed trades yet." />
              </div>
            ) : (
              <>
                <DataTable
                  columns={journalColumns}
                  data={closedPositions}
                  keyFn={(r) => `${r.ticker}-${r.exit_date}`}
                  searchable
                  searchPlaceholder="Search by ticker, reason, thesis..."
                  paginated
                  defaultPageSize={20}
                  onRowClick={(row) =>
                    setExpandedTicker(
                      expandedTicker === row.ticker ? null : row.ticker,
                    )
                  }
                />
                {expandedTicker && closedPositions.find(p => p.ticker === expandedTicker) && (
                  <div className="px-4 py-3 bg-gray-800/20 border-t border-gray-800/30 space-y-4">
                    <TradeDetail pos={closedPositions.find(p => p.ticker === expandedTicker)!} />
                    <TradeAnnotationPanel ticker={expandedTicker} />
                  </div>
                )}
              </>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
