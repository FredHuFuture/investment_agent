# Investment Analysis Agent — 技术方案 v4 (Final Architecture)

## 0. v3 → v4 变更摘要

|维度 |v3 |v4 |
|-----------|-----------------|-----------------------------------------------------------------|
|系统定位 |单次查询工具 |**持续监控的投资组合管理系统** |
|输入 |ticker + capital |**ticker + capital + 现有持仓结构** |
|数据源 |yfinance (免费) |**Phase 1-2: yfinance免费 → Phase 3+: FMP PIT (付费, 解决前视偏差)** |
|输出 |单ticker报告 |**单ticker报告 + Portfolio全局视图 + Exposure可视化** |
|预期vs实际 |trade_records简单记录|**Expected vs Actual ROI双轨追踪 + drift分析** |
|监控 |无 |**Monitoring Daemon (daily/weekly revaluation + catalyst alert)**|
|L3 Learning|Phase 3 |**延后至Phase 4+, 降优先级** |
|L2 Learning|Phase 3 |**提前至Phase 2, 与UI同步** |
|UI/可视化 |可选 |**Phase 2核心交付物** |

-----

## 1. 需求摘要

|维度 |决策 |
|-----|------------------------------------------------------------|
|资产 |美股个股 + BTC/Crypto |
|资金量级 |$200K–500K |
|工具定位 |持续监控 + 分析建议，手动交易 |
|投资周期 |按资产灵活调整 |
|美股策略 |实验阶段：基本面 / 技术面 / 多因子并行测试 |
|BTC策略|实验阶段：技术面+链上 / macro / 混合并行测试 |
|数据源 |Phase 1-2: yfinance + ccxt + FRED (免费) → Phase 3+: 按ROI升级FMP|
|学习优先级|L1权重自适应 → L2 Regime切换 → UI/图表 → (远期) L3推理 |

-----

## 2. 开源项目评估（同v3，此处从略）

决策不变：参考 ai-hedge-fund / Dexter / BettaFish / TradingAgents 的设计模式，
用统一的Python/LangGraph技术栈从头重建。

-----

## 3. 系统架构 v4
┌──────────────────────────────────────────────────────────────────────────────┐
│ Web UI (React) │
│ ┌───────────┐ ┌──────────────┐ ┌────────────────┐ ┌──────────────────────┐ │
│ │ Portfolio │ │ Single-Ticker│ │ Expected vs │ │ Monitoring │ │
│ │ Dashboard │ │ Analysis │ │ Actual ROI │ │ Alert Feed │ │
│ │ (Exposure)│ │ Report │ │ Tracker │ │ │ │
│ └───────────┘ └──────────────┘ └────────────────┘ └──────────────────────┘ │
└──────────────────────────────────┬───────────────────────────────────────────┘
 │
 ┌─────────────────────┼──────────────────────┐
 │ │ │
 ▼ ▼ ▼
┌────────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
│ On-demand │ │ Monitoring │ │ Learning │
│ Analysis Engine │ │ Daemon │ │ Engine │
│ │ │ │ │ │
│ ┌──────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────────┐ │
│ │ Portfolio │ │ │ │ Daily │ │ │ │ L1: Weight │ │
│ │ Context Mgr │ │ │ │ Revaluation │ │ │ │ Adaptation │ │
│ ├──────────────┤ │ │ ├─────────────┤ │ │ ├─────────────────┤ │
│ │ Analysis │ │ │ │ Catalyst │ │ │ │ L2: Regime │ │
│ │ Agents │ │ │ │ Scanner │ │ │ │ Switching │ │
│ ├──────────────┤ │ │ ├─────────────┤ │ │ ├─────────────────┤ │
│ │ Context Bus │ │ │ │ Exit │ │ │ │ (L3: Reasoning │ │
│ │ (Forum) │ │ │ │ Trigger │ │ │ │ — deferred) │ │
│ ├──────────────┤ │ │ │ Monitor │ │ │ └─────────────────┘ │
│ │ Validation │ │ │ ├─────────────┤ │ │ │
│ │ Agent │ │ │ │ Alert │ │ │ ┌─────────────────┐ │
│ ├──────────────┤ │ │ │ Dispatcher │ │ │ │ Expected vs │ ││ │ Decision │ │ │ └─────────────┘ │ │ │ Actual Tracker │ │
│ │ Layer │ │ │ │ │ └─────────────────┘ │
│ └──────────────┘ │ │ │ │ │
└────────────────────┘ └───────────────────┘ └───────────────────────┘
 │ │ │
 └─────────────────────┼──────────────────────┘
 │
 ▼
 ┌───────────────────┐
 │ Data Layer │
 │ FMP | ccxt | FRED │
 │ SQLite Store │
 └───────────────────┘

技术栈:

- Backend: Python 3.11+ / LangGraph / Claude API (Anthropic SDK)
- Data: yfinance (Phase 1-2) → FMP (Phase 3+) / ccxt / FRED / pandas_ta
- Store: SQLite (single-file, zero-ops)
- Frontend: React + TypeScript + Recharts/D3 (Phase 2+)
- Daemon: Python asyncio scheduler (APScheduler)

-----

## 4. Portfolio Context Manager [NEW v4]

### 4.1 为什么需要持仓上下文

v3的系统是stateless的——每次分析一个ticker，不知道你已经持有什么。这导致：

- 无法计算新建仓后的portfolio集中度风险
- 无法检测行业/资产类别暴露偏斜
- 无法知道”再买MSFT”意味着你的Tech exposure从30%涨到45%
- Position sizing没有portfolio层面的约束

v4将持仓结构作为一等公民输入。

### 4.2 持仓数据模型
# portfolio_context.py

@dataclass
class Position:
 ticker: str
 asset_type: str # 'stock' | 'btc' | 'eth' | 'cash'
 quantity: float
 avg_cost: float # 平均成本价
 current_price: float # 实时刷新
 market_value: float # quantity * current_price
 unrealized_pnl: float
 unrealized_pnl_pct: float
 sector: str | None # GICS sector (stocks only)
 industry: str | None # GICS industry (stocks only)
 entry_date: date
 holding_days: int
 # 系统生成的元数据
 original_analysis_id: int | None # 关联到哪次分析报告
 expected_return_pct: float | None # 当时系统的预期回报
 expected_hold_days: int | None # 当时系统建议的持有天数
 active_exit_triggers: ExitTriggers | None

@dataclass
class Portfolio:
 positions: list[Position]
 cash: float
 total_value: float # sum(positions.market_value) + cash
 # 实时计算的聚合指标
 stock_exposure_pct: float # 美股占比
 crypto_exposure_pct: float # Crypto占比
 cash_pct: float
 sector_breakdown: dict[str, float] # {"Technology": 0.35, "Healthcare": 0.15, ...}
 top_concentration: list[tuple[str, float]] # [("MSFT", 0.22), ("AAPL", 0.18), ...]
 beta_weighted: float | None # Portfolio beta vs SPX
 correlation_matrix: dict | None # 持仓间相关性

### 4.3 持仓管理接口
# 手动录入持仓（Phase 1: CLI）
$ advisor portfolio add --ticker MSFT --qty 200 --cost 415.50 --date 2026-02-10
$ advisor portfolio add --ticker BTC --qty 0.5 --cost 82000 --date 2026-01-20
$ advisor portfolio set-cash 150000

# 查看当前持仓
$ advisor portfolio show

# 资金增减与持仓缩放（核心规则）
# 本系统为“辅助决策+手动交易”模式，不直连券商账户。
# 当用户输入出入金（例如总资金从20万变为40万）：
$ advisor portfolio scale --multiplier 2.0
# 系统会自动等比例翻倍所有现有持仓的数量（或仅根据新比例计算 future sizing），完全依赖用户手动执行。

# 公司行动（拆股/除息）
# 仅作为消息 Alert 提示（如：“AAPL今日1拆4”）。系统不自动修改历史持仓价格，除非用户手动执行：
$ advisor portfolio split --ticker AAPL --ratio 4

### 4.4 Portfolio-Aware Analysis

当你请求分析一个新ticker时，系统自动叠加portfolio context:
class PortfolioAwareAnalyzer:
 """
 在v3的单ticker分析之上，叠加以下portfolio层面的检查:

 1. Concentration Check:
 如果买入GOOGL后Tech sector占比超过40% → 生成集中度警告
 2. Correlation Check:
 如果新持仓和现有持仓高度相关(ρ>0.8) → 提示分散化不足
 3. Position Sizing Adjustment:
 v3的position sizing只考虑单笔风险;
 v4额外考虑portfolio层面的max exposure constraints
 4. Marginal Risk Contribution:
 计算新持仓对portfolio整体vol/drawdown的边际贡献
 """

 def analyze(self, ticker: str, portfolio: Portfolio, capital_for_trade: float):
 # Step 1: 运行v3的所有agent分析 (fundamental, technical, etc.)
 base_analysis = self.run_agents(ticker)

 # Step 2: Portfolio overlay
 overlay = self.portfolio_overlay(ticker, portfolio, base_analysis)

 # Step 3: 调整position sizing
 adjusted_size = self.adjust_for_portfolio(
 base_size=base_analysis.position_size,
 portfolio=portfolio,
 overlay=overlay,
 )

 return AnalysisReport(
 base=base_analysis,
 portfolio_overlay=overlay,adjusted_position=adjusted_size,
 )

 def portfolio_overlay(self, ticker, portfolio, analysis) -> PortfolioOverlay:
 """
 输出:
 - pre_trade_exposure: 当前各sector/asset_class的占比
 - post_trade_exposure: 如果执行该交易后的占比
 - concentration_warnings: list[str]
 - correlation_with_existing: dict[str, float] # ticker vs 每个现有持仓的相关性
 - marginal_var: float # 新增持仓对portfolio VaR的边际贡献
 """

### 4.5 Exposure 可视化数据输出

系统输出结构化JSON供前端渲染，同时在CLI也能以文本形式展示:
@dataclass
class ExposureVisualization:
 """
 供前端Recharts/D3渲染的数据结构。
 CLI模式下以ASCII表格输出。
 """

 # 1. Sector Treemap (方块面积=占比)
 sector_treemap: list[dict]
 # [{"sector": "Technology", "value": 0.35, "tickers": ["MSFT","AAPL"],
 # "color": "#4A90D9"}, ...]

 # 2. Asset Class Donut Chart
 asset_class_donut: list[dict]
 # [{"name": "US Stocks", "value": 0.55}, {"name": "Crypto", "value": 0.15},
 # {"name": "Cash", "value": 0.30}]

 # 3. Pre vs Post Trade Comparison (grouped bar chart)
 exposure_comparison: list[dict]
 # [{"sector": "Technology", "before": 0.35, "after": 0.42, "delta": +0.07}, ...]

 # 4. Position Concentration (horizontal bar)
 concentration_bars: list[dict]
 # [{"ticker": "MSFT", "pct": 0.22}, {"ticker": "BTC", "pct": 0.15}, ...]

 # 5. Correlation Heatmap (持仓间)
 correlation_heatmap: dict
 # {"tickers": ["MSFT","AAPL","BTC"], "matrix": [[1,0.82,0.15],[0.82,1,0.12],[0.15,0.12,1]]}

前端渲染示意 (React + Recharts):
┌─ Portfolio Dashboard ──────────────────────────────────────────────────┐
│ │
│ ┌─ Asset Allocation ──────┐ ┌─ Sector Exposure ────────────────────┐ │
│ │ │ │ │ │
│ │ ┌──────────┐ │ │ Technology ████████████████ 35% │ │
│ │ │ US Stock │ │ │ Healthcare ██████ 15% │ │
│ │ │ 55% │ │ │ Financials ████ 10% │ │
│ │ │ ┌────┐ │ │ │ Energy ███ 8% │ │
│ │ │ │Cryp│ │ │ │ (Others) ██ 7% │ │
│ │ │ │15% │ │ │ │ Cash ████████████ 25% │ │
│ │ │ └────┘ │ │ │ │ │
│ │ │Cash: 30% │ │ │ ⚠ Technology > 30% threshold │ │
│ │ └──────────┘ │ │ │ │
│ └──────────────────────────┘ └──────────────────────────────────────┘ │
│ │
│ ┌─ Top Holdings ──────────────────────────────────────────────────────┐│
│ │ MSFT ████████████████████████ 22% +12.3% ($69,300) ││
│ │ BTC ████████████████ 15% -3.1% ($46,500) ││
│ │ AAPL ██████████████ 13% +8.7% ($40,300) ││
│ │ AMZN ████████ 8% +5.2% ($24,800) ││
│ │ (7 others) 17% ││
│ └─────────────────────────────────────────────────────────────────────┘│
│ │
│ ┌─ If you BUY GOOGL: Exposure Impact ────────────────────────────────┐│
│ │ Before After Delta ││
│ │ Technology 35% 42% +7% ⚠ EXCEEDS 40% LIMIT ││
│ │ Cash 30% 21% -9% ││
│ │ Max Position 22%(MSFT) 22%(MSFT) -- (GOOGL would be 4th at 9%) ││
│ │ Portfolio β 1.12 1.18 +0.06 ││
│ └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘

-----

## 5. Expected vs Actual ROI Tracking [NEW v4]

### 5.1 设计动机

v3只在trade结算后记录PnL。v4在 **建仓时就记录系统的预期**，然后持续追踪
预期与实际的偏差。这是评估”系统到底有没有用”的核心度量。

### 5.2 数据模型
-- 扩展 trade_records 表，增加 expected vs actual 双轨字段

CREATE TABLE trade_records (id INTEGER PRIMARY KEY,
 created_at DATETIME NOT NULL,

 -- Identity
 ticker TEXT NOT NULL,
 asset_type TEXT NOT NULL, -- 'stock' | 'btc'
 direction TEXT NOT NULL, -- 'LONG' | 'SHORT'

 -- EXPECTED (系统在出报告时的预测，建仓时锁定)
 expected_signal TEXT NOT NULL, -- 'BUY' | 'SELL' | 'HOLD'
 expected_confidence REAL NOT NULL, -- 0-100
 expected_entry_price REAL NOT NULL,
 expected_target_price REAL, -- TP1 or primary target
 expected_stop_loss REAL,
 expected_return_pct REAL, -- (target - entry) / entry
 expected_hold_days INTEGER, -- 建议持有天数
 expected_hold_range TEXT, -- "3-6 months" 原始文本
 expected_risk_pct REAL, -- (entry - stop) / entry
 expected_reward_risk REAL, -- expected_return / expected_risk
 skill_used TEXT,
 regime_at_entry TEXT,
 agent_signals JSON, -- 各agent的原始信号快照

 -- ACTUAL (实盘结果，逐步回填)
 actual_entry_price REAL, -- 你的实际入场价
 actual_entry_date DATE,
 actual_exit_price REAL,
 actual_exit_date DATE,
 actual_exit_reason TEXT, -- 'stop_loss' | 'target' | 'trailing'
 -- | 'catalyst_alert' | 'manual' | 'time_expiry'
 actual_return_pct REAL, -- 实际盈亏百分比
 actual_hold_days INTEGER,
 actual_pnl_amount REAL,

 -- DRIFT METRICS (系统自动计算)
 entry_drift_pct REAL, -- (actual_entry - expected_entry) / expected_entry
 return_drift_pct REAL, -- actual_return - expected_return
 hold_drift_days INTEGER, -- actual_hold - expected_hold
 outcome TEXT, -- 'WIN' | 'LOSS' | 'OPEN'
 outcome_vs_hold REAL, -- 超额收益 vs buy-and-hold

 -- 关联
 portfolio_snapshot_id INTEGER, -- 建仓时的portfolio快照
 monitoring_alerts JSON, -- 持仓期间触发的所有alerts
 validation_issues JSON
);

-- Portfolio 快照表 (每次建仓/平仓时自动记录)
CREATE TABLE portfolio_snapshots (
 id INTEGER PRIMARY KEY,
 timestamp DATETIME NOT NULL,
 total_value REAL,
 cash REAL,
 positions JSON, -- 所有持仓的snapshot
 sector_breakdown JSON,
 asset_class_breakdown JSON,
 trigger TEXT -- 'trade' | 'daily_reval' | 'manual'
);

### 5.3 Drift Analysis Engine
class DriftAnalyzer:
 """
 持续追踪系统预期 vs 实际结果的偏差，识别系统性bias。

 三种Drift:
 1. Entry Drift: 系统建议$418买，你实际$425买 → execution gap
 2. Return Drift: 系统预期+10%，实际+3% → forecast optimism
 3. Holding Drift: 系统建议30天，实际持有60天 → timing miscalibration
 """

 def compute_drift_stats(
 self,
 store: LearningStore,
 lookback: int = 50, # 最近N笔
 group_by: str = 'overall', # 'overall' | 'asset_type' | 'skill' | 'regime'
 ) -> DriftReport:
 """
 输出:
 - avg_return_drift: 平均回报偏差 (正=系统乐观, 负=系统悲观)
 - avg_hold_drift: 平均持有天数偏差 (正=实际比预期长)
 - confidence_calibration: 按confidence分桶的实际win rate
 e.g., confidence 70-80的信号，实际win rate是65% → 略乐观
 - optimism_by_regime: 哪个regime下系统最过度乐观？
 - optimism_by_agent: 哪个agent的预期最不准？
 - trend: drift是在收敛还是发散？(学习系统是否在改善？)
 """

 def generate_calibration_chart_data(self, store: LearningStore) -> dict:
 """
 生成 Confidence Calibration Chart 的数据。

 理想情况: confidence=70的信号，win rate应该≈70%
 实际情况: 通常LLM会过度自信

 输出JSON供Recharts渲染:
 {
 "data": [
 {"confidence_bucket": "50-60", "expected_win_rate": 55, "actual_win_rate": 48},
 {"confidence_bucket": "60-70", "expected_win_rate": 65, "actual_win_rate": 58},
 {"confidence_bucket": "70-80", "expected_win_rate": 75, "actual_win_rate": 66},{"confidence_bucket": "80-90", "expected_win_rate": 85, "actual_win_rate": 71},
 {"confidence_bucket": "90-100", "expected_win_rate": 95, "actual_win_rate": 73},
 ]
 }
 → 如果曲线低于对角线，说明系统系统性过度自信
 → L1 learning应该自动校准这个gap
 """

### 5.4 Expected vs Actual 可视化
┌─ Expected vs Actual ROI Dashboard ─────────────────────────────────────┐
│ │
│ ┌─ Scatter Plot: Expected vs Actual Return ──────────────────────────┐│
│ │ Actual ││
│ │ +30% │ ● ││
│ │ +20% │ ● ● ││
│ │ +10% │ ● ● ● ● ● ││
│ │ 0% │───●──●──────●─────────────────── Expected ││
│ │ -10% │ ● ● ││
│ │ -20% │● ││
│ │ └───────────────────────────────── ││
│ │ -10% 0% +10% +20% +30% ││
│ │ ││
│ │ ● above diagonal = system was conservative (good) ││
│ │ ● below diagonal = system was optimistic (bad) ││
│ │ Avg Drift: system is +3.2% optimistic on returns ││
│ └─────────────────────────────────────────────────────────────────────┘│
│ │
│ ┌─ Confidence Calibration ──┐ ┌─ Holding Period Drift ─────────────┐ │
│ │ Win% │ │ Days │ │
│ │ 100│ ╱ ideal │ │ 60│ ● │ │
│ │ 80│ ╱ │ │ 40│ ● ● ● ● │ │
│ │ 60│ ╱ ●──●──● │ │ 20│● ● ● ── expected │ │
│ │ 40│╱ ● actual │ │ 0│────────────────── │ │
│ │ 20│ │ │ -20│● │ │
│ │ └────────────── │ │ └────────────────── │ │
│ │ 50 60 70 80 90 │ │ Trade #1 ... #47 │ │
│ │ Confidence Bucket │ │ avg: held 8 days longer │ │
│ └────────────────────────────┘ └────────────────────────────────────┘ │
│ │
│ ┌─ Drift by Category ────────────────────────────────────────────────┐│
│ │ Return Drift Hold Drift Sample ││
│ │ US Stocks +2.1% +5 days 31 ││
│ │ BTC/Crypto +6.8% ⚠ +12 days ⚠ 16 ││
│ │ RISK_ON regime +1.5% +3 days 28 ││
│ │ RISK_OFF regime +8.2% ⚠ +15 days ⚠ 8 ││
│ │ trend_following +0.8% ✓ +2 days ✓ 22 ││
│ │ dcf_valuation +5.5% ⚠ +10 days 14 ││
│ │ ││
│ │ ⚠ = drift > 5% or > 10 days → system is significantly off ││
│ │ → Suggests: DCF skill in RISK_OFF regime is unreliable ││
│ └────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘

-----

## 6. Continuous Monitoring System [NEW v4]

### 6.1 设计动机

v3是”问一次答一次”的工具。但持仓期间世界在变——FOMC突然鹰派、公司发profit warning、
BTC交易所被黑。系统需要一个常驻后台进程，持续re-evaluate active positions。

### 6.2 Monitoring Daemon 架构
class MonitoringDaemon:
 """
 后台常驻进程，定时执行三类任务:

 1. Daily Revaluation (每交易日收盘后)
 - 更新所有持仓的current_price和unrealized PnL
 - 检查所有active exit triggers (stop loss, trailing stop, targets)
 - 更新portfolio exposure计算
 - 写入portfolio_snapshots表

 2. Catalyst Scanner (每4小时)
 - 扫描持仓相关的新闻/事件- 检查是否有宏观环境突变
 - 检查是否有即将到来的催化剂(财报、FOMC等)
 - 成本: 每次扫描 ~$0.02-0.05 (LLM调用)

 3. Weekly Deep Revaluation (每周末)
 - 对每个active position重新运行完整的agent分析
 - 对比当前信号vs建仓时信号: 是否发生方向反转？
 - 更新expected return和holding period建议
 - 生成Weekly Monitoring Report
 - 成本: 每position ~$0.10-0.15, 5 positions = ~$0.75
 """

 def __init__(self, config: MonitorConfig):
 self.scheduler = AsyncIOScheduler()
 self.store = LearningStore()
 self.portfolio = PortfolioManager()

 def start(self):
 # Daily: 美东时间 5:00 PM (收盘后)
 self.scheduler.add_job(
 self.daily_revaluation,
 'cron', hour=17, minute=0, timezone='US/Eastern',
 day_of_week='mon-fri'
 )
 # Catalyst scan: 每4小时 (交易时段)
 self.scheduler.add_job(
 self.catalyst_scan,
 'interval', hours=4
 )
 # Weekly deep reval: 周六上午
 self.scheduler.add_job(
 self.weekly_deep_revaluation,
 'cron', day_of_week='sat', hour=10
 )
 self.scheduler.start()

### 6.3 Daily Revaluation
async def daily_revaluation(self):
 """
 成本: $0 (不调LLM, 纯数据刷新和规则检查)
 耗时: < 30秒
 """
 portfolio = self.portfolio.load()

 for pos in portfolio.positions:
 # 1. 刷新价格
 pos.current_price = await self.data.get_price(pos.ticker)
 pos.unrealized_pnl_pct = (pos.current_price - pos.avg_cost) / pos.avg_cost

 # 2. 检查Exit Triggers
 alerts = []
 if pos.active_exit_triggers:
 t = pos.active_exit_triggers

 # Stop Loss
 if pos.current_price <= t.stop_loss_price:
 alerts.append(Alert(
 level='CRITICAL',
 type='STOP_LOSS_HIT',
 message=f'{pos.ticker} hit stop loss ${t.stop_loss_price:.2f} '
 f'(current: ${pos.current_price:.2f})',
 action='CLOSE POSITION — stop loss triggered',
 ))

 # Trailing Stop
 elif t.trailing_stop_pct:
 peak = self.store.get_peak_price(pos.ticker, since=pos.entry_date)
 trail_level = peak * (1 - t.trailing_stop_pct)
 if pos.current_price <= trail_level:
 alerts.append(Alert(
 level='CRITICAL',
 type='TRAILING_STOP_HIT',
 message=f'{pos.ticker} trailing stop triggered. '
 f'Peak: ${peak:.2f}, Trail: ${trail_level:.2f}',
 action='CLOSE POSITION — trailing stop triggered',
 ))

 # Target Price Hit
 for i, tp in enumerate(t.target_prices):
 if pos.current_price >= tp:
 alerts.append(Alert(
 level='INFO',
 type='TARGET_HIT',
 message=f'{pos.ticker} reached TP{i+1} ${tp:.2f}',
 action=f'Consider selling 1/{len(t.target_prices)} of position',
 ))

 # Time Expiry
 if pos.holding_days > (pos.expected_hold_days or 999) * 1.5:
 alerts.append(Alert(
 level='WARNING',
 type='TIME_OVERRUN',
 message=f'{pos.ticker} held {pos.holding_days}d vs '
 f'{pos.expected_hold_days}d expected (1.5x overrun)',
 action='Review: is the original thesis still intact?',
 ))

 # 3. 记录alert
 for alert in alerts:
 self.store.save_alert(pos.ticker, alert)
 await self.dispatch_alert(alert) # push notification / email

 # 4. Portfolio snapshot
 self.store.save_portfolio_snapshot(portfolio, trigger='daily_reval')

### 6.4 Catalyst Scanner
async def catalyst_scan(self):
 """
 每4小时运行一次。扫描可能影响持仓的突发事件。
 成本: ~$0.02-0.05/次 (1次LLM调用总结新闻)
 """
 portfolio = self.portfolio.load()
 active_tickers = [p.ticker for p in portfolio.positions]if not active_tickers:
 return

 # 1. 搜索持仓相关新闻
 news_results = await self.data.search_news(
 tickers=active_tickers,
 lookback_hours=4,
 )

 if not news_results:
 return

 # 2. LLM 评估影响
 prompt = f"""
 You are a risk analyst monitoring an active portfolio.

 CURRENT POSITIONS:
 {self._format_positions(portfolio.positions)}

 RECENT NEWS/EVENTS (last 4 hours):
 {self._format_news(news_results)}

 For each news item, assess:
 1. Which position(s) does it affect?
 2. Impact severity: NONE | LOW | MEDIUM | HIGH | CRITICAL
 3. Direction: POSITIVE | NEGATIVE | NEUTRAL
 4. Urgency: can wait for weekly review, or needs immediate attention?
 5. Recommended action (if any)

 Only flag items with MEDIUM or higher severity.
 Output as JSON array. If nothing material, return empty array [].
 """

 impacts = await llm.generate_structured(prompt)

 # 3. 生成alerts (只对MEDIUM+)
 for impact in impacts:
 if impact['severity'] in ('MEDIUM', 'HIGH', 'CRITICAL'):
 alert = Alert(
 level=impact['severity'],
 type='CATALYST_DETECTED',
 message=f"[{impact['ticker']}] {impact['summary']}",
 action=impact.get('recommended_action', 'Review position'),
 news_source=impact.get('source'),
 )
 self.store.save_alert(impact['ticker'], alert)
 await self.dispatch_alert(alert)

 # CRITICAL级别: 如果系统建议平仓，记录为potential forced exit
 if impact['severity'] == 'CRITICAL' and 'close' in impact.get('recommended_action', '').lower():
 self.store.flag_position_for_review(
 impact['ticker'],
 reason=f"CRITICAL catalyst: {impact['summary']}",
 suggested_exit=True,
 )

### 6.5 Weekly Deep Revaluation
async def weekly_deep_revaluation(self):
 """
 每周末对每个active position重新运行完整分析。
 成本: ~$0.10-0.15/position, 5 positions ≈ $0.75
 """
 portfolio = self.portfolio.load()
 weekly_report = WeeklyMonitoringReport()

 for pos in portfolio.positions:
 if pos.asset_type == 'cash':
 continue

 # 1. 重新运行完整agent分析
 current_analysis = await self.analyzer.analyze(pos.ticker)

 # 2. 获取建仓时的原始分析
 original_analysis = self.store.get_analysis(pos.original_analysis_id)

 # 3. 对比: 信号是否翻转？
 signal_change = self._compare_signals(original_analysis, current_analysis)

 # 4. 生成position review
 review = PositionReview(
 ticker=pos.ticker,
 days_held=pos.holding_days,
 unrealized_pnl_pct=pos.unrealized_pnl_pct,
 original_signal=original_analysis.signal,
 current_signal=current_analysis.signal,
 original_confidence=original_analysis.confidence,
 current_confidence=current_analysis.confidence,
 signal_changed=signal_change.direction_reversed,
 regime_changed=(original_analysis.regime != current_analysis.regime),
 alerts_this_week=self.store.get_alerts(pos.ticker, days=7),
 recommendation=self._generate_recommendation(pos, current_analysis, signal_change),
 )

 weekly_report.add_review(review)

 # 5. 如果信号翻转 → 高优先级alert
 if signal_change.direction_reversed:
 alert = Alert(
 level='HIGH',
 type='SIGNAL_REVERSAL',
 message=f'{pos.ticker}: signal flipped from {original_analysis.signal} '
 f'to {current_analysis.signal} (confidence: {current_analysis.confidence})',
 action='Strongly consider closing position',
 )
 await self.dispatch_alert(alert)

 # 6. 生成Weekly Report
 weekly_report.add_portfolio_summary(portfolio)
 weekly_report.add_expected_vs_actual_drift(
 self.drift_analyzer.compute_drift_stats(self.store)
 )
 self.store.save_weekly_report(weekly_report)
 return weekly_report

### 6.6 Alert Dispatchclass AlertDispatcher:
 """
 根据alert severity选择通知渠道:

 CRITICAL: push notification + email + UI banner
 HIGH: push notification + UI banner
 MEDIUM: UI banner + daily digest
 LOW/INFO: daily digest only

 Phase 1: 只写入SQLite, CLI查看
 Phase 2: email (SendGrid/SES)
 Phase 3: push notification (可选: Telegram bot / Slack webhook)
 """

### 6.7 Catalyst-Driven Exit Tracking

当monitoring daemon建议平仓且你执行时，这笔exit需要完整记录:
# 在trade_records中, actual_exit_reason = 'catalyst_alert'
# monitoring_alerts字段记录触发平仓的完整alert chain

# 示例:
{
 "alerts": [
 {"timestamp": "2026-03-15T14:00:00", "type": "CATALYST_DETECTED",
 "severity": "HIGH", "message": "MSFT announces major restructuring"},
 {"timestamp": "2026-03-15T18:00:00", "type": "SIGNAL_REVERSAL",
 "severity": "HIGH", "message": "Technical signal flipped to SELL"},
 {"timestamp": "2026-03-16T09:30:00", "type": "USER_ACTION",
 "message": "Position closed at $398.50"}
 ],
 "time_from_alert_to_exit": "19.5 hours",
 "price_at_first_alert": "$412.30",
 "price_at_exit": "$398.50",
 "alert_saved_loss": "+3.3% (vs not exiting)" # 估算
}

这些数据feed进Expected vs Actual tracker，用于评估monitoring系统的价值。

-----

## 7. Data Layer (分阶段升级策略)

### 7.1 策略: 免费起步, 按ROI升级

Phase 1-2使用yfinance + 免费API验证系统价值。当系统证明有效（Expected vs Actual
drift收敛, 回测Sharpe > 1）后, 再升级到付费数据源解决数据质量问题。

yfinance的已知局限 (接受但记录):

- 财报数据不是Point-in-Time, 回测中存在前视偏差
- 无SLA, 偶尔被Yahoo rate limit
- 分钟线数据有限
- 这些问题在Phase 1-2可以接受: 实时分析不受PIT影响 (用的就是当前数据),
 回测结果需要标注 “⚠ non-PIT data, results may be optimistic”

### 7.2 数据源矩阵

#### Phase 1-2: 免费方案 (月成本 $0 + LLM ~$5)

|数据类型 |来源 |成本 |说明 |
|----------------|---------------------------------|------------|-----------------------|
|**美股价格** |yfinance |$0 |日线可靠, 历史20年+ |
|**美股基本面** |yfinance (financials) |$0 |季报/年报, 非PIT ⚠ |
|**技术指标** |pandas_ta (本地) |$0 |基于yfinance价格计算 |
|**BTC/Crypto价格**|ccxt (Binance) |$0 |多时间框架K线 |
|**链上数据** |Glassnode免费tier / blockchain.info|$0 |MVRV, SOPR等 |
|**Funding Rate**|ccxt |$0 |永续合约 |
|**宏观** |FRED API (fredapi) |$0 |利率, M2, CPI, DXY, PIT ✓|
|**新闻/情绪** |Web search + LLM |~$0.03/query|Claude NLP |
|**Fear & Greed**|alternative.me |$0 |BTC专用 |

总月度数据成本: $0 (仅LLM调用 ~$5/mo)

#### Phase 3+: 付费升级路径 (按ROI决定)

|升级 |成本 |解决什么问题 |升级条件 |
|------------------|------|-------------------------|------------------------------|
|FMP Basic |$20/mo|Point-in-Time财报, 消除回测前视偏差|系统已证明有效, 需要可靠的回测数据 |
|FMP Premium |$50/mo|更高rate limit |monitoring daemon跑满rate limit时|
|Glassnode Advanced|$30/mo|更多链上指标 |BTC策略表现好, 需要更多信号 |
|Polygon.io |$30/mo|实时tick-level数据 |短线策略需要更高频数据时 |

### 7.3 Point-in-Time: 为什么Phase 3再升级
免费阶段的回测注意事项:

yfinance财报数据不是Point-in-Time:
 - 它返回最新修订版, 不是当时公布版
 - 回测中Fundamental Agent可能"偷看"了修订后的数字
 - 影响: DCF估值偏差1-5%, 回测Sharpe可能虚高

缓解措施 (Phase 1-2):
 1. 回测报告自动标注 "⚠ non-PIT data"
 2. Fundamental Agent的回测信号需要额外discount
 3. Technical Agent回测不受影响 (价格数据是PIT的)
 4. 重点关注Technical + On-chain的回测结果 (不受PIT影响)
 5. 实时分析不受影响 (当前数据就是当前数据)

升级到FMP后的价值:
 - 回测前视偏差消除, Fundamental策略的回测才可信
 - Insider trading数据 (Form 4) 可加入Sentiment Agent
 - SEC filing解析可增强Fundamental Agent深度
 - Stable API with SLA, monitoring daemon更可靠

### 7.4 Data Layer抽象 (支持平滑切换)
class DataProvider(ABC):
 """
 抽象数据接口, 使得从yfinance切换到FMP只需改配置, 不改业务代码。

 Phase 1: YFinanceProvider
 Phase 3: FMPProvider (implements same interface)
 """

 @abstractmethod
 async def get_price(self, ticker: str, period: str) -> pd.DataFrame: ...

 @abstractmethodasync def get_financials(self, ticker: str, period: str) -> dict: ...

 @abstractmethod
 async def get_insider_trades(self, ticker: str) -> list | None: ...

 @abstractmethod
 def is_point_in_time(self) -> bool:
 """回测引擎用此标记是否需要加non-PIT disclaimer"""
 ...

class YFinanceProvider(DataProvider):
 def is_point_in_time(self) -> bool:
 return False # 回测报告会自动标注

class FMPProvider(DataProvider):
 def is_point_in_time(self) -> bool:
 return True

-----

## 8. Analysis Agents (同v3核心设计, 简述)

### 8.1 Agent清单

|Agent |资产 |依赖 |说明 |
|------------------------|---|-------------------------------|----------------------------------|
|A: Fundamental Valuation|美股 |yfinance→FMP + LLM |DCF, ratios, sector comparison |
|B: Technical Analysis |通用 |yfinance/ccxt + pandas_ta + LLM|多时间框架, 形态识别 |
|C: Sentiment & Catalyst |通用 |Web search + LLM |BettaFish式多源情绪 + 催化剂日历 |
|D: BTC On-chain |BTC|ccxt + Glassnode + LLM |MVRV, SOPR, funding, exchange flow|
|E: Macro Liquidity |共享 |FRED + LLM |M2, DXY, VIX, yield curve, regime |

### 8.2 Context Sharing Bus (同v3)

两轮执行: Round 1并行 → Moderator汇总 → 条件性Round 2

### 8.3 Skill System (同v3)

YAML模块化策略, 热插拔, 支持per-regime统计。

### 8.4 v4变更: Agent接收Portfolio Context

每个agent在分析时额外接收当前portfolio状态:
class AgentInput:
 ticker: str
 market_data: MarketData
 portfolio: Portfolio | None # [NEW v4]
 regime: Regime
 learned_weights: dict
 approved_rules: list

# Agent prompt中会包含:
# "Current portfolio: 35% Tech, 15% Crypto, 30% Cash.
# Buying {ticker} would increase Tech to 42%."
# → agent可以在reasoning中考虑portfolio层面的因素

-----

## 9. Decision Layer

### 9.1 Signal Aggregator (同v3, 使用learned weights)

### 9.2 Validation Agent (同v3)

### 9.3 Position Sizing (v4: Portfolio-Constrained)
def calculate_position_size(
 capital_for_trade: float,
 signal_confidence: float,
 asset_volatility: float,
 stop_loss_pct: float,
 validation_result: ValidationResult,
 portfolio: Portfolio, # [NEW v4]
 portfolio_constraints: dict, # [NEW v4]
) -> PositionSize:
 """
 v3的基础sizing之上, 新增portfolio层面约束:

 portfolio_constraints = {
 "max_single_position": 0.15, # 单持仓不超过15% of total
 "max_sector_exposure": 0.40, # 单行业不超过40%
 "max_crypto_exposure": 0.25, # Crypto不超过25%
 "max_correlation_penalty": 0.20, # 高相关持仓额外扣减20%
 }

 新增检查:
 1. 如果买入后sector exposure超限 → 缩减到刚好不超
 2. 如果和现有持仓相关性>0.8 → 额外扣减max_correlation_penalty
 3. 如果portfolio beta > 1.5 → 限制aggressive positions
 """

### 9.4 Holding Period Estimator (同v3)

### 9.5 Exit Signal Engine (v4: 与Monitoring Daemon联动)

Exit triggers不再是静态设置——monitoring daemon会持续检查并生成alert。

-----

## 10. Adaptive Learning System

### 10.1 架构变更 (v4 vs v3)

|层 |v3 |v4 |
|---------------------------|-------|-------------------------------|
|L1: Weight Adaptation |Phase 2|Phase 2 (不变) |
|L2: Regime Switching |Phase 3|**Phase 2 (提前)** |
|L3: Reasoning Self-Optimize|Phase 3|**Phase 4+ (延后, 低优先级)** |
|Expected vs Actual Tracker |无 |**Phase 1 数据采集, Phase 2 分析+UI**|

### 10.2 L1: Weight Adaptation (同v3)

EWMA追踪agent表现 → 自动调权。冷启动10笔, 正常30笔, 高置信100笔。

### 10.3 L2: Regime-Aware Strategy Switching (提前至Phase 2)

提前的理由: Regime切换是纯规则引擎, 不依赖LLM, 但对策略有效性影响巨大。
回测数据显示momentum策略在RISK_OFF环境下Sharpe可能从1.5跌到-0.3。
越早引入, 越早避免在错误regime下使用错误策略。

实现同v3, 此处从略。

### 10.4 L3: Reasoning Self-Optimize (延后至Phase 4+)

延后的理由:

- 依赖LLM反思, 结果不可靠, 需要人工审核
- 前几个Phase的数据量不足以支撑有意义的error pattern分析
- L1 + L2 + Expected vs Actual Tracker已经覆盖了80%的学习价值
- 开发资源应优先投入UI/可视化和Monitoring Daemon

L3在Phase 4+作为可选增强引入。设计同v3, 不再重复。

### 10.5 Learning Store Schema (v4完整版)
-- 1. trade_records: 见 Section 5.2 (含expected vs actual双轨)

-- 2. agent_performance (同v3)
CREATE TABLE agent_performance (agent_name TEXT,
 asset_type TEXT,
 regime TEXT,
 window_days INTEGER,
 total_signals INTEGER,
 correct_signals INTEGER,
 win_rate REAL,
 avg_confidence REAL,
 confidence_calibration REAL,
 avg_pnl_when_followed REAL,
 updated_at DATETIME
);

-- 3. regime_history (同v3)
CREATE TABLE regime_history (
 date DATE PRIMARY KEY,
 regime TEXT,
 vix REAL,
 m2_growth REAL,
 yield_curve REAL,
 dxy REAL,
 btc_funding REAL
);

-- 4. skill_performance (同v3)
CREATE TABLE skill_performance (
 skill_name TEXT,
 asset_type TEXT,
 regime TEXT,
 backtest_sharpe REAL,
 backtest_win_rate REAL,
 live_sharpe REAL,
 live_win_rate REAL,
 sample_size INTEGER,
 updated_at DATETIME
);

-- 5. portfolio_snapshots (NEW v4)
CREATE TABLE portfolio_snapshots (
 id INTEGER PRIMARY KEY,
 timestamp DATETIME NOT NULL,
 trigger TEXT, -- 'trade' | 'daily_reval' | 'weekly_deep' | 'manual'
 total_value REAL,
 cash REAL,
 positions JSON,
 sector_breakdown JSON,
 asset_class_breakdown JSON
);

-- 6. monitoring_alerts (NEW v4)
CREATE TABLE monitoring_alerts (
 id INTEGER PRIMARY KEY,
 timestamp DATETIME NOT NULL,
 ticker TEXT,
 alert_type TEXT, -- 'STOP_LOSS_HIT' | 'TRAILING_STOP_HIT' | 'TARGET_HIT'
 -- | 'CATALYST_DETECTED' | 'SIGNAL_REVERSAL' | 'TIME_OVERRUN'
 severity TEXT, -- 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO'
 message TEXT,
 recommended_action TEXT,
 acknowledged BOOLEAN DEFAULT FALSE,
 acted_upon BOOLEAN DEFAULT FALSE,
 trade_record_id INTEGER -- 如果导致平仓, 关联到哪笔trade
);

-- 7. drift_snapshots (NEW v4)
CREATE TABLE drift_snapshots (
 id INTEGER PRIMARY KEY,
 computed_at DATETIME,
 lookback_trades INTEGER,
 group_by TEXT, -- 'overall' | 'asset_type' | 'skill' | 'regime'
 group_value TEXT, -- e.g., 'stock', 'trend_following', 'RISK_ON'
 avg_return_drift REAL,
 avg_hold_drift_days REAL,
 calibration_data JSON, -- confidence bucket → actual win rate
 sample_size INTEGER
);

-- 8. reasoning_lessons (v3 L3, 延后, 表结构保留)
CREATE TABLE reasoning_lessons (
 id INTEGER PRIMARY KEY,
 created_at DATETIME,
 source_trade_ids JSON,
 error_pattern TEXT,
 lesson TEXT,
 action_rule TEXT,
 status TEXT DEFAULT 'proposed', -- 'proposed'|'approved'|'rejected'
 applied_count INTEGER DEFAULT 0,
 effectiveness REAL
);

-----

## 11. Output Format (v4: 含Portfolio Overlay)

### 11.1 Single-Ticker Analysis Report
═══════════════════════════════════════════════════════════════════════
 INVESTMENT ANALYSIS REPORT — GOOGL
 Date: 2026-03-08 | Total Portfolio: $400,000 | Cash Available: $120,000
═══════════════════════════════════════════════════════════════════════

VERDICT: BUY (Confidence: 68/100)

VALIDATION:
 ✓ Data/Logic consistent | ⚠ Confidence 74→68 (FOMC proximity)

AGENT SIGNALS (learned weights):
 Fundamental: BUY (80) [wt: 38%] — 12% below DCF fair value
 Technical: BUY (65) [wt: 25%] — consolidating near support, MACD turning
 Sentiment: HOLD (55) [wt: 22%] — antitrust overhang, but cloud growth strong
 Macro: BUY (70) [wt: 15%] — rate cuts favor growth

REGIME: RISK_ON (21 days) | Skill: trend_following (Sharpe 1.5 in this regime)

─── PORTFOLIO IMPACT ─────────────────────────────────────────────────

 Current Portfolio:
 US Stocks: 55% | Crypto: 15% | Cash: 30%
 Sector: Tech 35%, Healthcare 12%, Financials 8%, Other 15%

 If BUY GOOGL ($36,000 position):
 US Stocks: 55% → 64% Cash: 30% → 21%
 Tech: 35% → 44% ⚠ EXCEEDS 40% SECTOR LIMIT

 Correlation with existing:
 vs MSFT: ρ=0.78 (high) vs AAPL: ρ=0.72 (moderate-high)
 → Marginal diversification benefit: LOW

 Portfolio β: 1.12 → 1.19 (+0.07)

 PORTFOLIO ADJUSTMENT:
 Original sizing: 200 shares ($36,000, 9% of portfolio)
 Adjusted sizing: 140 shares ($25,200, 6.3%)
 Reason: Tech sector cap (40%) and high correlation with MSFT

─── POSITION PLAN ────────────────────────────────────────────────────

 Entry: $178–$182 range, limit order
 Size: 140 shares @ ~$180 = $25,200 (6.3% of portfolio)
 Risk at Stop: $2,520 (0.63% of portfolio)

 Expected Return: +14% ($3,528) over 3–5 months
 Stop Loss: $162 (-10%)
 Targets: TP1 $198 (+10%) | TP2 $214 (+19%) | TP3 $230 (+28%)

 Holding: 3–5 months | Next Review: 2026-04-24 (post Q1 earnings)

─── MONITORING PLAN ──────────────────────────────────────────────────

 Daily: price check, exit trigger scan
 Catalyst watch: Q1 earnings (Apr 24), antitrust ruling (est. May)
 Weekly: full signal revaluation

 RISK FLAGS:
 ⚠ Tech sector 44% post-trade (above 40% limit → position reduced)
 ⚠ High correlation with MSFT (ρ=0.78) → limited diversification
 ⚠ Antitrust ruling pending → binary event risk
═══════════════════════════════════════════════════════════════════════

### 11.2 Weekly Monitoring Report
═══════════════════════════════════════════════════════════════════════
 WEEKLY MONITORING REPORT — Week of 2026-03-02
 Portfolio Value: $412,300 (+3.1% WoW) | 5 Active Positions
═══════════════════════════════════════════════════════════════════════

PORTFOLIO HEALTH:
 Total Unrealized PnL: +$12,300 (+3.1%)
 Cash: $118,500 (28.7%)
 Max Drawdown This Week: -1.2% (Wed, recovered Thu)

POSITION REVIEWS:
 ┌──────┬────────┬──────────┬──────────┬────────────┬───────────────┐
 │Ticker│ P&L │ Signal │ Signal │ Expected │ Status │
 │ │ │ (entry) │ (now) │ vs Actual │ │
 ├──────┼────────┼──────────┼──────────┼────────────┼───────────────┤
 │ MSFT │ +12.3% │ BUY (85) │ BUY (78) │ +10% exp │ ✓ On track │
 │ │ 26d │ │ │ +12% act │ (exceeding) │
 ├──────┼────────┼──────────┼──────────┼────────────┼───────────────┤
 │ AAPL │ +4.1% │ BUY (72) │ HOLD(58) │ +15% exp │ ⚠ Confidence │
 │ │ 18d │ │ │ +4% act │ dropping │
 ├──────┼────────┼──────────┼──────────┼────────────┼───────────────┤
 │ BTC │ -3.1% │ BUY (70) │ BUY (65) │ +20% exp │ ⚠ Underwater │
 │ │ 47d │ │ │ -3% act │ exp hold 30-60│
 ├──────┼────────┼──────────┼──────────┼────────────┼───────────────┤
 │ F │ +1.8% │ BUY (60) │ HOLD(52) │ +8% exp │ ⚠ Weak signal │
 │ │ 12d │ │ │ +2% act │ │
 ├──────┼────────┼──────────┼──────────┼────────────┼───────────────┤
 │GOOGL │ -0.5% │ BUY (68) │ BUY (66) │ +14% exp │ ✓ Just opened │
 │ │ 3d │ │ │ -1% act │ │
 └──────┴────────┴──────────┴──────────┴────────────┴───────────────┘

ALERTS THIS WEEK:
 Mon: [INFO] MSFT hit TP1 $460 → consider selling 1/3
 Wed: [HIGH] AAPL: signal confidence dropped below 60 threshold
 Fri: [MEDIUM] BTC funding rate spiked to 0.06% → crowded long

EXPECTED vs ACTUAL DRIFT (rolling 47 trades):
 Avg Return Drift: +3.2% (system is optimistic by 3.2%)
 Avg Hold Drift: +8 days (positions held longer than expected)
 Trend: drift narrowing over last 10 trades (learning working?)

EXPOSURE SNAPSHOT:
 Technology: 38% (↓ from 42% last week, MSFT partial sell)
 Crypto: 13%
 Automotive: 5%
 Cash: 29%
═══════════════════════════════════════════════════════════════════════

-----

## 12. Frontend Architecture (v4: Phase 2 Core Deliverable)

### 12.1 技术选型

|组件 |选择 |理由 |
|---------|--------------------------------|----------------------------|
|Framework|React + TypeScript |你已熟悉 (Huly技术栈) |
|Charts |Recharts (primary) + D3 (custom)|Recharts覆盖80%需求, D3做heatmap等|
|State |React Query (TanStack Query) |自动fetch/cache/revalidate ||API |FastAPI (Python backend) |和LangGraph/data layer同进程 |
|Styling |Tailwind CSS |快速迭代 |
|Optional |Tauri wrapper |Phase 4, 桌面app |

### 12.2 页面结构
App
├── /dashboard ← Portfolio Dashboard (landing page)
│ ├── Asset Allocation Donut
│ ├── Sector Treemap
│ ├── Top Holdings Bars
│ ├── Portfolio Value Curve (time series)
│ └── Active Alerts Feed
│
├── /analyze/:ticker ← Single-Ticker Analysis
│ ├── Verdict Banner
│ ├── Agent Signals Panel
│ ├── Portfolio Impact Panel (before/after exposure)
│ ├── Position Plan
│ ├── Monitoring Plan
│ └── Risk Flags
│
├── /monitor ← Monitoring Hub
│ ├── Active Positions Table (sortable, filterable)
│ ├── Alert Timeline
│ ├── Position Detail Drill-down
│ └── Weekly Report Viewer
│
├── /performance ← Expected vs Actual ROI
│ ├── Scatter Plot (expected vs actual return)
│ ├── Confidence Calibration Chart
│ ├── Holding Period Drift Chart
│ ├── Drift by Category Table
│ ├── Cumulative PnL Curve (strategy vs buy-and-hold)
│ └── Monthly Learning Report
│
├── /backtest ← Backtest Runner
│ ├── Skill Selector
│ ├── Parameter Controls
│ ├── Results: equity curve, metrics, trade log
│ └── Comparison Mode (multi-skill overlay)
│
└── /settings ← Configuration
 ├── Portfolio Management (add/edit/import positions)
 ├── Risk Parameters (sector caps, position limits)
 ├── Monitoring Schedule (daemon controls)
 ├── API Keys (LLM, FMP optional)
 └── Learning Controls (L1 weights, L2 regime thresholds)

### 12.3 关键图表规格

|图表 |库 |数据源 |刷新频率 |
|--------------------------|----------------------------------|--------------------------------|-----------------|
|Asset Allocation Donut |Recharts PieChart |portfolio_snapshots |实时 (on page load)|
|Sector Treemap |D3 treemap |portfolio + yfinance sector data|实时 |
|Exposure Before/After |Recharts BarChart (grouped) |analysis engine |每次分析 |
|Correlation Heatmap |D3 custom |yfinance historical prices |每次分析 |
|Expected vs Actual Scatter|Recharts ScatterChart |trade_records |每次trade更新 |
|Confidence Calibration |Recharts LineChart + ReferenceLine|drift_snapshots |每周 |
|Portfolio Equity Curve |Recharts AreaChart |portfolio_snapshots |每日 |
|Alert Timeline |Custom React component |monitoring_alerts |实时 |

-----

## 13. Build Plan (v4 最终版)

### Phase 1: Core Engine + Data Foundation (Week 1–3)

目标: 端到端能对一个ticker生成报告, 含portfolio context

|任务 |优先级|说明 |
|---------------------------------------|---|---------------------------------|
|DataProvider抽象层 |P0 |支持未来从yfinance平滑切换到FMP |
|yfinance + ccxt + FRED集成 |P0 |免费数据源, 零成本 |
|Portfolio Context Manager |P0 |CLI持仓管理 + 自动exposure计算 |
|Technical Agent |P0 |通用, 基于yfinance/ccxt价格数据 |
|Fundamental Agent |P0 |基于yfinance financials (标注non-PIT)|
|Signal Aggregator (默认权重) |P0 |简单加权, 无Forum |
|Position Sizing (portfolio-constrained)|P0 |含sector cap检查 |
|Exit Trigger Engine |P0 |规则引擎, 不依赖LLM |
|trade_records表 (含expected vs actual字段) |P0 |SQLite |
|portfolio_snapshots表 |P0 |每次交易时自动snapshot |
|CLI报告输出 |P0 |含portfolio overlay section |
|规则引擎回测器 |P1 |Layer 1 (技术指标), 标注⚠non-PIT |