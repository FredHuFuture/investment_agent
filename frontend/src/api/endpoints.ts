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

// Weights
export const getWeights = () => apiGet<WeightsData>("/weights");

// Summary
export const getLatestSummary = () =>
  apiGet<SummaryResponse>("/summary/latest");
export const generateSummary = () =>
  apiPost<SummaryResponse>("/summary/generate", {});

// Daemon
export const getDaemonStatus = () => apiGet<DaemonStatus>("/daemon/status");
export const daemonRunOnce = (job: "daily" | "weekly") =>
  apiPost<Record<string, unknown>>("/daemon/run-once", { job });

// Notifications
export async function testEmailNotification(): Promise<{data: {sent: boolean; message?: string}; warnings: string[]}> {
  return apiPost<{sent: boolean; message?: string}>('/alerts/test-email', {});
}

export async function testTelegramNotification(): Promise<{data: {sent: boolean; message?: string}; warnings: string[]}> {
  return apiPost<{sent: boolean; message?: string}>('/alerts/test-telegram', {});
}
