// ---------------------------------------------------------------------------
// Portfolio
// ---------------------------------------------------------------------------
export interface Position {
  ticker: string;
  asset_type: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  entry_date: string;
  sector: string | null;
  industry: string | null;
  cost_basis: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  holding_days: number;
  // Thesis fields (optional - null if no thesis recorded)
  thesis_text: string | null;
  expected_return_pct: number | null;
  expected_hold_days: number | null;
  target_price: number | null;
  stop_loss: number | null;
  // Lifecycle fields (Sprint 8)
  status: string;
  exit_price: number | null;
  exit_date: string | null;
  exit_reason: string | null;
  realized_pnl: number | null;
}

export interface ClosePositionResult {
  ticker: string;
  quantity: number;
  avg_cost: number;
  exit_price: number;
  exit_date: string;
  exit_reason: string;
  realized_pnl: number;
  return_pct: number;
}

export interface ThesisResponse {
  ticker: string;
  thesis_text: string | null;
  expected_return_pct: number | null;
  expected_hold_days: number | null;
  target_price: number | null;
  stop_loss: number | null;
  hold_days_elapsed: number;
  hold_drift_days: number | null;
  return_drift_pct: number | null;
}

export interface Portfolio {
  positions: Position[];
  cash: number;
  total_value: number;
  stock_exposure_pct: number;
  crypto_exposure_pct: number;
  cash_pct: number;
  sector_breakdown: Record<string, number>;
  top_concentration: Array<[string, number]>;
}

// ---------------------------------------------------------------------------
// Price History (OHLCV)
// ---------------------------------------------------------------------------
export interface OhlcvPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// ---------------------------------------------------------------------------
// Analysis
// ---------------------------------------------------------------------------
export interface AgentSignal {
  agent_name: string;
  ticker: string;
  signal: string;
  confidence: number;
  reasoning: string;
  metrics: Record<string, number>;
  timestamp?: string;
  warnings?: string[];
}

export interface AnalysisMetrics {
  raw_score: number;
  consensus_score: number;
  buy_count: number;
  sell_count: number;
  hold_count: number;
  regime: string;
  weights_used: Record<string, number>;
  agent_contributions: Record<string, number>;
  buy_threshold: number;
  sell_threshold: number;
}

export interface AnalysisResult {
  ticker: string;
  asset_type: string;
  final_signal: string;
  final_confidence: number;
  regime: string;
  agent_signals: AgentSignal[];
  reasoning: string;
  metrics: AnalysisMetrics;
  warnings: string[];
  ticker_info: Record<string, unknown>;
  portfolio_impact?: PortfolioImpact;
}

// ---------------------------------------------------------------------------
// Backtest
// ---------------------------------------------------------------------------
export interface BacktestTrade {
  entry_date: string;
  exit_date: string | null;
  signal: string;
  entry_price: number;
  exit_price: number | null;
  pnl_pct: number | null;
  exit_reason: string | null;
  holding_days: number | null;
  confidence: number;
}

export interface SignalLogEntry {
  date: string;
  signal: string;
  confidence: number;
  raw_score: number;
}

export interface BacktestMetrics {
  total_return_pct: number;
  annualized_return_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  win_rate: number;
  total_trades: number;
  sortino_ratio?: number;
  calmar_ratio?: number;
  profit_factor?: number;
  avg_win_pct?: number;
  avg_loss_pct?: number;
  avg_holding_days?: number;
  [key: string]: number | undefined;
}

export interface BacktestResult {
  metrics: BacktestMetrics;
  trades: BacktestTrade[];
  trades_count: number;
  equity_curve: Array<{ date: string; equity: number; price?: number }>;
  signals_log: SignalLogEntry[];
}

// Batch API returns Record<ticker, Record<agentComboKey, metrics>>
export type BatchResponse = Record<string, Record<string, BacktestMetrics>>;

// Flattened row for UI display
export interface BatchRow {
  ticker: string;
  agents: string;
  metrics: BacktestMetrics;
}

// ---------------------------------------------------------------------------
// Signals
// ---------------------------------------------------------------------------
export interface SignalHistoryEntry {
  id: number;
  ticker: string;
  final_signal: string;
  final_confidence: number;
  raw_score: number;
  consensus_score: number;
  regime: string | null;
  agent_signals: unknown[];
  reasoning: string;
  created_at: string;
}

export interface AccuracyStats {
  total_signals: number;
  resolved_count: number;
  win_count: number;
  loss_count: number;
  win_rate: number | null;
  avg_confidence: number | null;
  by_signal: Record<string, { count: number; win_rate: number | null }>;
  by_asset_type: Record<string, { count: number; win_rate: number | null }>;
  by_regime: Record<string, { count: number; win_rate: number | null }>;
}

export interface CalibrationBucket {
  bucket: string;
  count: number;
  accuracy_pct: number;
}

export interface AgentPerformanceEntry {
  agent: string;
  total_signals: number;
  directional_accuracy_pct: number;
  agreement_rate_pct: number;
  avg_confidence: number;
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------
export interface Alert {
  id: number;
  ticker: string | null;
  alert_type: string;
  severity: string;
  message: string;
  acknowledged: number;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Weights
// ---------------------------------------------------------------------------
export interface WeightsData {
  weights: Record<string, Record<string, number>>;
  crypto_factor_weights: Record<string, number>;
  buy_threshold: number;
  sell_threshold: number;
  source: string;
  sample_size: number;
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
export interface SummaryResponse {
  summary_text: string;
  generated_at: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  positions_covered: string[];
}

// ---------------------------------------------------------------------------
// Catalysts / Sentiment
// ---------------------------------------------------------------------------
export interface NewsHeadline {
  title: string;
  source: string;
  published_at: string;
  url: string | null;
}

export interface SentimentResult {
  signal: string;
  confidence: number;
  sentiment_score: number;
  catalysts: string[];
  reasoning: string;
}

export interface CatalystData {
  headlines: NewsHeadline[];
  sentiment: SentimentResult | null;
}

// ---------------------------------------------------------------------------
// Portfolio Impact / Position Sizing
// ---------------------------------------------------------------------------
export interface PortfolioImpact {
  ticker: string;
  current_sector_pct: number;
  projected_sector_pct: number;
  sector: string | null;
  concentration_warning: string | null;
  correlated_positions: Array<{ ticker: string; correlation: number }>;
  correlation_warning: string | null;
  suggested_quantity: number | null;
  suggested_allocation_pct: number;
  max_position_pct: number;
  before_exposure: Record<string, number>;
  after_exposure: Record<string, number>;
}

export interface CorrelationEntry {
  ticker: string;
  existing_ticker: string;
  correlation: number;
  period_days: number;
  warning: string | null;
}

// ---------------------------------------------------------------------------
// Daemon
// ---------------------------------------------------------------------------
export interface DaemonJobStatus {
  last_run: string | null;
  status: string;
}

export type DaemonStatus = Record<string, DaemonJobStatus>;

// ---------------------------------------------------------------------------
// Analytics / Performance
// ---------------------------------------------------------------------------
export interface ValueHistoryPoint {
  date: string;
  total_value: number;
  cash: number;
  invested: number;
}

export interface PerformanceSummary {
  total_realized_pnl: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  best_trade: { ticker: string; return_pct: number; pnl: number } | null;
  worst_trade: { ticker: string; return_pct: number; pnl: number } | null;
  avg_hold_days: number;
  total_trades: number;
}

export interface MonthlyReturn {
  month: string;
  pnl: number;
  trade_count: number;
  return_pct: number;  // NEW
}

export interface TradePerformer {
  ticker: string;
  return_pct: number;
  pnl: number;
  entry_date: string;
  exit_date: string;
}

export interface TopPerformers {
  best: TradePerformer[];
  worst: TradePerformer[];
}

// ---------------------------------------------------------------------------
// Watchlist
// ---------------------------------------------------------------------------
export interface WatchlistItem {
  id: number;
  ticker: string;
  asset_type: string;
  notes: string;
  target_buy_price: number | null;
  alert_below_price: number | null;
  added_at: string;
  last_analysis_at: string | null;
  last_signal: string | null;
  last_confidence: number | null;
}

// ---------------------------------------------------------------------------
// Risk Analytics
// ---------------------------------------------------------------------------
export interface PortfolioRisk {
  daily_volatility: number;
  annualized_volatility: number;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown_pct: number;
  current_drawdown_pct: number;
  var_95: number;
  cvar_95: number;
  best_day_pct: number;
  worst_day_pct: number;
  positive_days: number;
  negative_days: number;
  data_points: number;
}

export interface CorrelationData {
  correlation_matrix: Record<string, number>;
  avg_correlation: number;
  high_correlation_pairs: Array<[string, string, number]>;
  concentration_risk: "HIGH" | "MODERATE" | "LOW";
  tickers: string[];
}

// ---------------------------------------------------------------------------
// Benchmark Comparison
// ---------------------------------------------------------------------------
export interface BenchmarkPoint {
  date: string;
  portfolio_indexed: number;
  benchmark_indexed: number;
}

export interface BenchmarkComparison {
  series: BenchmarkPoint[];
  benchmark_ticker: string;
  portfolio_return_pct: number;
  benchmark_return_pct: number;
  alpha_pct: number;
  data_points: number;
}
