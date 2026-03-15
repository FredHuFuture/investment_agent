import { apiGet, apiPost, apiPut, apiPatch, apiDelete } from "./client";
import type {
  Portfolio,
  Position,
  ClosePositionResult,
  AnalysisResult,
  BacktestResult,
  BatchResponse,
  AccuracyStats,
  CalibrationBucket,
  AgentPerformanceEntry,
  SignalHistoryEntry,
  Alert,
  WeightsData,
  DaemonStatus,
  ThesisResponse,
  SummaryResponse,
  OhlcvPoint,
  CatalystData,
  PortfolioImpact,
  CorrelationEntry,
  ValueHistoryPoint,
  PerformanceSummary,
  MonthlyReturn,
  TopPerformers,
  WatchlistItem,
  PortfolioRisk,
  CorrelationData,
  BenchmarkComparison,
  RegimeResult,
  UpdateThesisBody,
  CumulativePnlPoint,
  PositionPnlPoint,
  AlertTimelinePoint,
  SignalAccuracyTrendPoint,
  AgentAgreementEntry,
  DrawdownPoint,
  RollingSharpePoint,
  MonthlyHeatmapCell,
  TradeAnnotation,
  StressScenario,
  PortfolioProfile,
  RegimeHistoryPoint,
  WatchlistAlertConfig,
  LessonTagStats,
  DaemonRunEntry,
  AlertStats,
  AnalysisHistoryEntry,
} from "./types";

// Portfolio
export const getPortfolio = () => apiGet<Portfolio>("/portfolio");
export const addPosition = (body: {
  ticker: string;
  asset_type?: string;
  quantity: number;
  avg_cost: number;
  entry_date: string;
  sector?: string;
  industry?: string;
  thesis_text?: string;
  expected_return_pct?: number;
  expected_hold_days?: number;
  target_price?: number;
  stop_loss?: number;
}) => apiPost<{ id: number }>("/portfolio/positions", body);
export const removePosition = (ticker: string) =>
  apiDelete<{ removed: boolean }>(`/portfolio/positions/${ticker}`);
export const setCash = (amount: number) =>
  apiPut<{ cash: number }>("/portfolio/cash", { amount });
export const scalePortfolio = (multiplier: number) =>
  apiPost<{ multiplier: number }>("/portfolio/scale", { multiplier });
export const applySplit = (ticker: string, ratio: number) =>
  apiPost<{ applied: boolean }>("/portfolio/split", { ticker, ratio });
export const getThesis = (ticker: string) =>
  apiGet<ThesisResponse>(`/portfolio/positions/${ticker}/thesis`);
export const closePosition = (
  ticker: string,
  body: { exit_price: number; exit_reason?: string; exit_date?: string },
) => apiPost<ClosePositionResult>(`/portfolio/positions/${ticker}/close`, body);
export const updateThesis = (ticker: string, body: UpdateThesisBody) =>
  apiPut<ThesisResponse>(`/portfolio/positions/${ticker}/thesis`, body);
export const getPositionHistory = () =>
  apiGet<Position[]>("/portfolio/history");

// Analysis
export const analyzeTicker = (
  ticker: string,
  assetType = "stock",
  adaptiveWeights = false,
) =>
  apiGet<AnalysisResult>(
    `/analyze/${ticker}?asset_type=${assetType}&adaptive_weights=${adaptiveWeights}`,
  );

export const analyzeTickerCustom = (
  ticker: string,
  assetType: string,
  weights: Record<string, number>,
) =>
  apiPost<AnalysisResult>(`/analyze/${ticker}`, {
    ticker,
    asset_type: assetType,
    weights,
  });

export const getPriceHistory = (
  ticker: string,
  assetType = "stock",
  period = "1y",
) =>
  apiGet<OhlcvPoint[]>(
    `/analyze/${ticker}/price-history?asset_type=${assetType}&period=${period}`,
  );

export async function getCatalysts(
  ticker: string,
  assetType = "stock",
): Promise<{ data: CatalystData; warnings: string[] }> {
  const res = await apiGet<CatalystData>(
    `/analyze/${ticker}/catalysts?asset_type=${assetType}`,
  );
  return res;
}

export async function getPositionSize(
  ticker: string,
  assetType = "stock",
  targetAllocationPct = 0.05,
) {
  return apiGet<PortfolioImpact>(
    `/analyze/${ticker}/position-size?asset_type=${assetType}&target_allocation_pct=${targetAllocationPct}`,
  );
}

export async function getCorrelation(
  ticker: string,
  assetType = "stock",
) {
  return apiGet<CorrelationEntry[]>(
    `/analyze/${ticker}/correlation?asset_type=${assetType}`,
  );
}

// Backtest
export const runBacktest = (body: {
  ticker: string;
  start_date: string;
  end_date: string;
  asset_type?: string;
  initial_capital?: number;
  rebalance_frequency?: string;
  agents?: string[];
  position_size_pct?: number;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  buy_threshold?: number;
  sell_threshold?: number;
}) => apiPost<BacktestResult>("/backtest", body);

export const runBatchBacktest = (body: {
  tickers: string[];
  agent_combos: string[][];
  start_date: string;
  end_date: string;
  initial_capital?: number;
  position_size_pct?: number;
  rebalance_frequency?: string;
}) => apiPost<BatchResponse>("/backtest/batch", body);

// Signals
export const getSignalHistory = (params?: {
  ticker?: string;
  signal?: string;
  limit?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.ticker) qs.set("ticker", params.ticker);
  if (params?.signal) qs.set("signal", params.signal);
  if (params?.limit) qs.set("limit", String(params.limit));
  const q = qs.toString();
  return apiGet<SignalHistoryEntry[]>(`/signals/history${q ? `?${q}` : ""}`);
};
export const getAccuracyStats = () =>
  apiGet<AccuracyStats>("/signals/accuracy");
export const getCalibration = () =>
  apiGet<CalibrationBucket[]>("/signals/calibration");
export const getAgentPerformance = () =>
  apiGet<Record<string, AgentPerformanceEntry>>("/signals/agents");
export const getAccuracyTrend = (window = 30) =>
  apiGet<SignalAccuracyTrendPoint[]>(`/signals/accuracy-trend?window=${window}`);
export const getAgentAgreement = (lookback = 100) =>
  apiGet<AgentAgreementEntry[]>(`/signals/agent-agreement?lookback=${lookback}`);

// Alerts
export const getAlerts = (params?: {
  ticker?: string;
  severity?: string;
  acknowledged?: number;
  limit?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.ticker) qs.set("ticker", params.ticker);
  if (params?.severity) qs.set("severity", params.severity);
  if (params?.acknowledged !== undefined)
    qs.set("acknowledged", String(params.acknowledged));
  if (params?.limit) qs.set("limit", String(params.limit));
  const q = qs.toString();
  return apiGet<Alert[]>(`/alerts${q ? `?${q}` : ""}`);
};
export const acknowledgeAlert = (id: number) =>
  apiPatch<{ id: number; acknowledged: number }>(
    `/alerts/${id}/acknowledge`,
  );
export const deleteAlert = (id: number) =>
  apiDelete<{ id: number; deleted: boolean }>(`/alerts/${id}`);
export const runMonitorCheck = () =>
  apiPost<Record<string, unknown>>("/monitor/check");
export const batchAcknowledgeAlerts = (alertIds: number[]) =>
  apiPatch<{ acknowledged_count: number }>("/alerts/batch-acknowledge", { alert_ids: alertIds });
export const getAlertTimeline = (days = 30) =>
  apiGet<AlertTimelinePoint[]>(`/alerts/timeline?days=${days}`);

// Weights
export const getWeights = () => apiGet<WeightsData>("/weights");

// Summary
export const getLatestSummary = () =>
  apiGet<SummaryResponse>("/summary/latest");
export const generateSummary = () =>
  apiPost<SummaryResponse>("/summary/generate", {});

// Daemon
export const getDaemonStatus = () => apiGet<DaemonStatus>("/daemon/status");
export const daemonRunOnce = (job: "daily" | "weekly" | "regime" | "watchlist") =>
  apiPost<Record<string, unknown>>("/daemon/run-once", { job });

// Notifications
export async function testEmailNotification(): Promise<{data: {sent: boolean; message?: string}; warnings: string[]}> {
  return apiPost<{sent: boolean; message?: string}>('/alerts/test-email', {});
}

export async function testTelegramNotification(): Promise<{data: {sent: boolean; message?: string}; warnings: string[]}> {
  return apiPost<{sent: boolean; message?: string}>('/alerts/test-telegram', {});
}

// Analytics
export const getValueHistory = (days = 90) =>
  apiGet<ValueHistoryPoint[]>(`/analytics/value-history?days=${days}`);
export const getPerformanceSummary = () =>
  apiGet<PerformanceSummary>("/analytics/performance");
export const getMonthlyReturns = () =>
  apiGet<MonthlyReturn[]>("/analytics/monthly-returns");
export const getTopPerformers = (limit = 5) =>
  apiGet<TopPerformers>(`/analytics/top-performers?limit=${limit}`);
export const getCumulativePnl = () =>
  apiGet<CumulativePnlPoint[]>("/analytics/cumulative-pnl");
export const getPositionPnlHistory = (ticker: string) =>
  apiGet<PositionPnlPoint[]>(`/analytics/position-pnl/${ticker}`);

// Risk Analytics
export const getPortfolioRisk = (days = 90) =>
  apiGet<PortfolioRisk>(`/analytics/risk?days=${days}`);
export const getPortfolioCorrelations = (lookbackDays = 90) =>
  apiGet<CorrelationData>(`/analytics/correlations?lookback_days=${lookbackDays}`);
export const getBenchmarkComparison = (days = 90, benchmark = "SPY") =>
  apiGet<BenchmarkComparison>(`/analytics/benchmark?days=${days}&benchmark=${benchmark}`);

// Regime
export const getRegime = () =>
  apiGet<RegimeResult>("/regime/current");

// Watchlist
export const getWatchlist = () => apiGet<WatchlistItem[]>("/watchlist");
export const addToWatchlist = (body: {
  ticker: string;
  asset_type?: string;
  notes?: string;
  target_buy_price?: number;
  alert_below_price?: number;
}) => apiPost<WatchlistItem>("/watchlist", body);
export const removeFromWatchlist = (ticker: string) =>
  apiDelete<{ ticker: string; removed: boolean }>(`/watchlist/${ticker}`);
export const updateWatchlistItem = (
  ticker: string,
  body: { notes?: string; target_buy_price?: number; alert_below_price?: number },
) => apiPut<WatchlistItem>(`/watchlist/${ticker}`, body);
export const analyzeWatchlistTicker = (ticker: string) =>
  apiPost<{ watchlist_item: WatchlistItem; analysis: AnalysisResult }>(
    `/watchlist/${ticker}/analyze`,
    {},
  );
export const analyzeAllWatchlist = () =>
  apiPost<{
    results: Array<{
      ticker: string;
      signal: string | null;
      confidence: number | null;
      raw_score: number | null;
      status: string;
      error?: string;
    }>;
    total: number;
    success_count: number;
  }>("/watchlist/analyze-all", {});

// Portfolio sector filter
export const getPositionsBySector = (sector: string) =>
  apiGet<Position[]>(`/portfolio/sector/${encodeURIComponent(sector)}`);

// Performance analytics (Sprint 29)
export const getDrawdownSeries = (days = 90) =>
  apiGet<DrawdownPoint[]>(`/analytics/drawdown-series?days=${days}`);
export const getRollingSharpe = (days = 90, window = 30) =>
  apiGet<RollingSharpePoint[]>(`/analytics/rolling-sharpe?days=${days}&window=${window}`);
export const getMonthlyHeatmap = () =>
  apiGet<MonthlyHeatmapCell[]>("/analytics/monthly-heatmap");

// Journal annotations (Sprint 29)
export const getTradeAnnotations = (ticker: string) =>
  apiGet<TradeAnnotation[]>(`/journal/annotations/${encodeURIComponent(ticker)}`);
export const createTradeAnnotation = (
  ticker: string,
  body: { annotation_text: string; lesson_tag?: string },
) => apiPost<TradeAnnotation>(`/journal/annotations/${encodeURIComponent(ticker)}`, body);

// Risk stress test (Sprint 29)
export const getStressScenarios = () =>
  apiGet<StressScenario[]>("/risk/stress-test");

// Portfolio profiles (Sprint 30)
export const listProfiles = () =>
  apiGet<PortfolioProfile[]>("/portfolios");
export const createProfile = (body: { name: string; description?: string; initial_cash?: number }) =>
  apiPost<PortfolioProfile>("/portfolios", body);
export const updateProfile = (id: number, body: { name?: string; description?: string }) =>
  apiPut<PortfolioProfile>(`/portfolios/${id}`, body);
export const deleteProfile = (id: number) =>
  apiDelete<{ deleted: boolean }>(`/portfolios/${id}`);
export const setDefaultProfile = (id: number) =>
  apiPost<{ default_profile_id: number }>(`/portfolios/${id}/set-default`, {});

// Regime history (Sprint 30)
export const getRegimeHistory = (days = 90) =>
  apiGet<RegimeHistoryPoint[]>(`/regime/history?days=${days}`);

// Watchlist alert config (Sprint 30)
export const setWatchlistAlertConfig = (
  ticker: string,
  body: { alert_on_signal_change?: boolean; min_confidence?: number; alert_on_price_below?: number | null; enabled?: boolean },
) => apiPut<WatchlistAlertConfig>(`/watchlist/${ticker}/alerts`, body);
export const getWatchlistAlertConfigs = () =>
  apiGet<WatchlistAlertConfig[]>("/watchlist/alert-configs");

// Journal lesson analytics (Sprint 30)
export const getLessonTagStats = () =>
  apiGet<LessonTagStats[]>("/journal/lesson-stats");

// Daemon run history (Sprint 32)
export const getDaemonHistory = (jobName?: string, limit = 20) => {
  const qs = new URLSearchParams();
  if (jobName) qs.set("job_name", jobName);
  qs.set("limit", String(limit));
  return apiGet<DaemonRunEntry[]>(`/daemon/history?${qs.toString()}`);
};

// Alert analytics (Sprint 32)
export const getAlertStats = (days = 30) =>
  apiGet<AlertStats>(`/alerts/stats?days=${days}`);

// Analysis history (Sprint 32)
export const getAnalysisHistory = (params?: {
  ticker?: string;
  signal?: string;
  limit?: number;
  offset?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.ticker) qs.set("ticker", params.ticker);
  if (params?.signal) qs.set("signal", params.signal);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const q = qs.toString();
  return apiGet<AnalysisHistoryEntry[]>(`/analysis/history${q ? `?${q}` : ""}`);
};
export const getAnalyzedTickers = () =>
  apiGet<string[]>("/analysis/history/tickers");
