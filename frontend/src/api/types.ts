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
  // Advanced metrics (Sprint 26)
  profit_factor: number | null;
  expectancy: number | null;
  max_consecutive_wins: number;
  max_consecutive_losses: number;
}

export interface CumulativePnlPoint {
  date: string;
  cumulative_pnl: number;
  trade_count: number;
}

export interface PositionPnlPoint {
  date: string;
  price: number;
  cost_basis: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
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
// Regime Detection
// ---------------------------------------------------------------------------
export interface RegimeResult {
  regime: string;
  confidence: number;
  indicators: Record<string, unknown>;
  vix_current?: number;
  vix_sma_20?: number;
  yield_curve_spread?: number;
  fed_funds_rate?: number;
  fed_funds_trend?: string;
  m2_yoy_growth?: number;
}

// ---------------------------------------------------------------------------
// Thesis Update (request body)
// ---------------------------------------------------------------------------
export interface UpdateThesisBody {
  thesis_text?: string | null;
  target_price?: number | null;
  stop_loss?: number | null;
  expected_hold_days?: number | null;
  expected_return_pct?: number | null;
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

// ---------------------------------------------------------------------------
// Sprint 27 types
// ---------------------------------------------------------------------------
export interface AlertTimelinePoint {
  date: string;
  count: number;
  severity_breakdown: Record<string, number>;
}

export interface SignalAccuracyTrendPoint {
  date: string;
  accuracy_pct: number;
  sample_size: number;
}

export interface AgentAgreementEntry {
  agent_a: string;
  agent_b: string;
  agreement_pct: number;
  sample_size: number;
}

// ---------------------------------------------------------------------------
// Sprint 29 types
// ---------------------------------------------------------------------------
export interface DrawdownPoint {
  date: string;
  drawdown_pct: number;
}

export interface RollingSharpePoint {
  date: string;
  sharpe: number;
}

export interface MonthlyHeatmapCell {
  year: number;
  month: number;
  return_pct: number;
}

export interface TradeAnnotation {
  id: number;
  position_ticker: string;
  annotation_text: string;
  lesson_tag: string | null;
  created_at: string;
}

export interface StressScenario {
  name: string;
  description: string;
  portfolio_impact_pct: number;
  affected_positions: Array<{ ticker: string; impact_pct: number }>;
}

// ---------------------------------------------------------------------------
// Sprint 30 types
// ---------------------------------------------------------------------------
export interface PortfolioProfile {
  id: number;
  name: string;
  description: string;
  cash: number;
  created_at: string;
  is_default: number;
}

export interface RegimeHistoryPoint {
  date: string;
  regime: string;
  confidence: number;
  duration_days: number;
}

export interface WatchlistAlertConfig {
  ticker: string;
  alert_on_signal_change: boolean;
  min_confidence: number;
  alert_on_price_below: number | null;
  enabled: boolean;
}

export interface LessonTagStats {
  tag: string;
  count: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  avg_return_pct: number;
}

// ---------------------------------------------------------------------------
// Sprint 32 types
// ---------------------------------------------------------------------------
export interface DaemonRunEntry {
  id: number;
  job_name: string;
  status: string;
  started_at: string;
  duration_ms: number | null;
  result_json: string | null;
  error_message: string | null;
  created_at: string;
}

export interface AlertStats {
  total_count: number;
  unacknowledged_count: number;
  ack_rate_pct: number;
  by_ticker: Array<{ ticker: string; count: number; severity_breakdown: Record<string, number> }>;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
  avg_alerts_per_day: number;
}

export interface AnalysisHistoryEntry {
  id: number;
  ticker: string;
  asset_type: string;
  final_signal: string;
  final_confidence: number;
  regime: string | null;
  raw_score: number;
  consensus_score: number;
  agent_signals: Array<{ agent_name: string; signal: string; confidence: number; reasoning?: string }>;
  reasoning: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Sprint 33 types
// ---------------------------------------------------------------------------
export interface MonteCarloResult {
  percentiles: Record<string, number[]>;
  horizon_days: number;
  simulations: number;
  dates: string[];
  current_value: number;
}

export interface DailyReturn {
  return_pct: number;
  return_dollars: number;
  date: string;
  previous_value: number;
  current_value: number;
}

export interface SystemInfo {
  status: string;
  db_path: string;
  version: string;
  total_positions: number;
  total_closed: number;
  total_signals: number;
  total_alerts: number;
}

// ---------------------------------------------------------------------------
// Sprint 34 types
// ---------------------------------------------------------------------------
export interface NotificationConfig {
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password: string;
  smtp_enabled: boolean;
  telegram_bot_token: string;
  telegram_chat_id: string;
  telegram_enabled: boolean;
  notify_critical: boolean;
  notify_high: boolean;
  notify_warning: boolean;
  notify_info: boolean;
}

export interface PositionEvent {
  type: "entry" | "signal" | "alert" | "thesis_change" | "annotation" | "exit";
  date: string;
  title: string;
  detail: string | null;
  severity: string | null;
  metadata: Record<string, unknown>;
}

export interface ActivityFeedEntry {
  type: "daemon_run" | "alert" | "signal" | "trade";
  timestamp: string;
  title: string;
  detail: string | null;
  severity: string | null;
  icon: string;
}

// ---------------------------------------------------------------------------
// Sprint 35 types
// ---------------------------------------------------------------------------
export interface BulkImportResult {
  imported: number;
  skipped: number;
  errors: Array<{ ticker: string; reason: string }>;
}

export interface WatchlistTarget {
  ticker: string;
  target_buy_price: number;
  current_price: number;
  distance_pct: number;
  last_signal: string | null;
  last_confidence: number | null;
}

export interface PerformanceAttribution {
  ticker: string;
  sector: string | null;
  pnl: number;
  pnl_pct: number;
  contribution_pct: number;
  status: string;
}

// ---------------------------------------------------------------------------
// Sprint 36 types
// ---------------------------------------------------------------------------
export interface DividendEntry {
  id: number;
  ticker: string;
  amount_per_share: number;
  total_amount: number;
  ex_date: string;
  pay_date: string | null;
  created_at: string;
}

export interface DividendSummary {
  entries: DividendEntry[];
  total_dividends: number;
  yield_on_cost_pct: number;
}

export interface SnapshotComparison {
  date_a: string;
  date_b: string;
  total_value_a: number;
  total_value_b: number;
  value_change: number;
  value_change_pct: number;
  positions_added: string[];
  positions_removed: string[];
  positions_changed: Array<{
    ticker: string;
    value_a: number;
    value_b: number;
    change_pct: number;
  }>;
}

export interface BulkWatchlistResult {
  added: number;
  skipped: number;
  errors: Array<{ ticker: string; reason: string }>;
}

// ---------------------------------------------------------------------------
// Sprint 37 types
// ---------------------------------------------------------------------------
export interface EarningsEvent {
  ticker: string;
  earnings_date: string;
  days_until: number;
  estimate_eps: number | null;
  actual_eps: number | null;
  source: string;
}

export interface PortfolioGoal {
  id: number;
  label: string;
  target_value: number;
  target_date: string | null;
  created_at: string;
}

export interface PositionNote {
  id: number;
  ticker: string;
  note_text: string;
  created_at: string;
}

export interface SectorPerformanceEntry {
  sector: string;
  total_pnl: number;
  total_pnl_pct: number;
  position_count: number;
  best_ticker: string | null;
  worst_ticker: string | null;
}
