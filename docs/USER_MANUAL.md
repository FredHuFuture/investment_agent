# Investment Agent 使用手册

> **版本**: v5 · Sprint 38 | **测试覆盖**: 889 tests (517 BE + 372 FE) | **API 端点**: ~100 | **页面**: 15

---

## 目录

1. [系统概述](#1-系统概述)
2. [安装与启动](#2-安装与启动)
3. [配置说明](#3-配置说明)
4. [Web 界面操作指南](#4-web-界面操作指南)
   - [4.1 Dashboard 仪表盘](#41-dashboard-仪表盘)
   - [4.2 Analysis 分析](#42-analysis-分析)
   - [4.3 Portfolio 投资组合](#43-portfolio-投资组合)
   - [4.4 Position Detail 持仓详情](#44-position-detail-持仓详情)
   - [4.5 Watchlist 观察列表](#45-watchlist-观察列表)
   - [4.6 Performance 业绩表现](#46-performance-业绩表现)
   - [4.7 Risk 风险管理](#47-risk-风险管理)
   - [4.8 Journal 交易日志](#48-journal-交易日志)
   - [4.9 Backtest 回测](#49-backtest-回测)
   - [4.10 Signals 信号追踪](#410-signals-信号追踪)
   - [4.11 Monitoring 监控告警](#411-monitoring-监控告警)
   - [4.12 Weights 权重分布](#412-weights-权重分布)
   - [4.13 Daemon 后台任务](#413-daemon-后台任务)
   - [4.14 Analysis History 分析历史](#414-analysis-history-分析历史)
   - [4.15 Settings 系统设置](#415-settings-系统设置)
5. [CLI 命令行操作](#5-cli-命令行操作)
6. [多智能体分析系统](#6-多智能体分析系统)
7. [告警与通知](#7-告警与通知)
8. [数据导出](#8-数据导出)
9. [日常使用建议](#9-日常使用建议)
10. [API 端点参考](#10-api-端点参考)
11. [常见问题](#11-常见问题)

---

## 1. 系统概述

Investment Agent 是一个自托管的投资组合监控与分析系统, 核心理念: **"会反击的投资日记"** -- 追踪你的投资论点, 监控持仓, 在现实偏离计划时及时提醒。

### 核心能力

| 功能模块 | 说明 |
|----------|------|
| **多智能体分析** | 6 个专业 Agent 并行分析, 生成 BUY/HOLD/SELL 信号 |
| **投资组合管理** | 持仓跟踪、论点管理、目标价/止损管理、多组合支持 |
| **风险监控** | 波动率、Sharpe、VaR、最大回撤、相关性矩阵、压力测试 |
| **回测引擎** | Walk-forward 回测 (无前视偏差), 14+ 指标 |
| **交易日志** | 已平仓记录、教训标签、绩效洞察 |
| **自动化监控** | 后台守护进程, 自动价格检查与告警生成 |
| **通知系统** | 邮件 (SMTP) + Telegram 实时告警 |

### 支持的资产类型

- **美股**: AAPL, MSFT, NVDA, TSLA, GOOG, SPY 等
- **加密货币**: BTC (比特币), ETH (以太坊)

### 技术架构

```
Frontend (React 18 + TypeScript + Tailwind CSS)
    |
    | HTTP/JSON (port 3000 -> 8000)
    |
Backend (FastAPI + Python 3.11+)
    |
    | aiosqlite (async)
    |
Database (SQLite + WAL mode)
```

---

## 2. 安装与启动

### 2.1 系统要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 18+ | 前端构建/运行 |
| npm | 随 Node.js | 前端包管理 |

### 2.2 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/FredHuFuture/investment_agent.git
cd investment_agent

# 2. 安装 Python 后端
pip install --pre -e ".[dev]"

# 3. 安装前端依赖
cd frontend && npm install && cd ..

# 4. (可选) 导入演示数据
python seed.py
```

### 2.3 启动服务

**方式一: PowerShell (Windows)**

```powershell
.\run.ps1                  # 同时启动前后端
.\run.ps1 -Backend         # 仅后端 (port 8000)
.\run.ps1 -Frontend        # 仅前端 (port 3000)
```

**方式二: 手动启动**

```bash
# 终端 1: 后端 API
uvicorn api.app:app --port 8000 --reload

# 终端 2: 前端
cd frontend && npm run dev
```

### 2.4 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端界面 | http://localhost:3000 | Web 仪表盘 |
| API 文档 | http://localhost:8000/docs | Swagger 交互文档 |
| 数据库 | `data/investment_agent.db` | SQLite 文件 |

---

## 3. 配置说明

### 3.1 环境变量

在项目根目录创建 `.env` 文件:

```env
# 宏观经济数据 (免费注册: https://fred.stlouisfed.org)
FRED_API_KEY=your_key_here

# Claude API (可选, 用于情绪分析和 AI 摘要)
ANTHROPIC_API_KEY=your_key_here

# 邮件通知 (可选)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_TO_EMAILS=you@email.com

# Telegram 通知 (可选)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3.2 优雅降级

系统在缺少 API Key 时不会崩溃, 而是跳过对应功能:

| 缺少的 Key | 影响 | 替代行为 |
|------------|------|----------|
| `FRED_API_KEY` | MacroAgent 不可用 | 仅用 Technical + Fundamental 分析 |
| `ANTHROPIC_API_KEY` | SentimentAgent + SummaryAgent 不可用 | 仅用规则型 Agent |
| SMTP 配置 | 邮件通知不可用 | 可用 Telegram 或仅 Web 告警 |
| Telegram 配置 | Telegram 通知不可用 | 可用邮件或仅 Web 告警 |

---

## 4. Web 界面操作指南

### 全局功能

- **快捷键**: `Ctrl+K` (Windows) / `Cmd+K` (Mac) 打开命令面板, 快速跳转页面
- **主题切换**: 支持 Dark / Light / System 三种主题 (Settings 页面切换)
- **侧边栏**: 可折叠导航, 移动端自动切换为抽屉式
- **自动刷新**: Dashboard/Portfolio 页面每 60 秒自动刷新数据
- **错误处理**: 所有页面含 Retry 按钮, API 失败时可一键重试

---

### 4.1 Dashboard 仪表盘

**路由**: `/` (首页)

仪表盘是系统的中央控制台, 一页纵览投资组合全貌。

#### 顶部指标卡片 (5 张)

| 指标 | 说明 |
|------|------|
| Portfolio Value | 当前组合总市值 |
| Unrealized P&L | 未实现盈亏 (含百分比) |
| Realized P&L | 已实现盈亏 |
| Cash | 可用现金余额 |
| Daily Return | 今日涨跌 |

#### 功能模块

| 模块 | 说明 |
|------|------|
| **Watchlist Targets Banner** | 观察列表中接近目标买入价的标的 (距目标 < 10%) |
| **Earnings Calendar** | 持仓标的未来 60 天内的财报日历, 颜色标记天数远近 |
| **Top Movers** | 今日涨跌幅最大的持仓 |
| **Signal Summary** | 最近信号汇总 (BUY / SELL / HOLD 计数) |
| **Risk Summary** | 风险概要 (波动率、VaR、最大回撤) |
| **Activity Feed** | 最近活动流 (分析、告警、守护进程运行) |
| **Portfolio Value Chart** | 30 天组合价值走势 (面积图) |
| **Regime Timeline** | 市场状态时间线 (牛市/熊市/震荡/高波动/避险) |
| **Sector Allocation** | 行业配置图 |
| **Thesis Drift Alerts** | 论点偏移告警 (价格超目标 10%、跌破止损、持有超时) |
| **Open Positions** | 持仓简表 (Ticker / Price / P&L%) |
| **Recent Alerts** | 最新告警列表 (按严重程度着色) |
| **Quick Actions** | 快捷操作按钮 (Analyze, Health Check, Signals) |
| **Weekly Summary** | 每周 AI 摘要 (需 Anthropic API Key) |

---

### 4.2 Analysis 分析

**路由**: `/analyze`

对单个标的或多个标的进行多维度智能分析。

#### 单一分析模式

1. 在输入框输入 Ticker (如 `AAPL`), 选择资产类型 (Stock / BTC / ETH)
2. 点击 **Analyze** 或按 Enter
3. 系统并行运行所有可用 Agent, 生成综合信号

**快捷按钮**: SPY, AAPL, MSFT, NVDA, TSLA, BTC -- 点击直接分析

#### 分析结果面板

| 区域 | 内容 |
|------|------|
| **Signal Badge** | BUY (绿) / HOLD (黄) / SELL (红) + 置信度百分比 |
| **Signal Strength Gauge** | 信号强度仪表盘 (原始分数 vs 共识) |
| **Key Metrics** | 价格、市值、52 周范围、行业等 |
| **Agent Breakdown** | 每个 Agent 的独立信号、置信度、关键指标 |
| **Catalyst Panel** | 催化剂/新闻分析 (需 Anthropic Key) |
| **Price History** | 历史价格走势图 |
| **Portfolio Impact** | 如果买入对组合的影响估算 |
| **Weight Adjuster** | 手动调整各 Agent 权重后重新计算 |

#### 对比模式

1. 切换到 **Compare** 标签
2. 添加 2-5 个标的
3. 并排对比分析结果 (信号、指标、图表)

#### 分析后操作

- **Add to Portfolio**: 分析结果满意? 直接添加到投资组合

---

### 4.3 Portfolio 投资组合

**路由**: `/portfolio`

管理所有持仓的核心页面。

#### 顶部指标

| 指标 | 说明 |
|------|------|
| Portfolio Value | 组合总值 (现金 + 市值) |
| Unrealized P&L | 所有持仓未实现盈亏 |
| Realized P&L | 已平仓累计盈亏 |
| Cash | 可用现金 |

#### Goal Tracker (目标追踪)

- 设定投资组合目标 (如 "年底达到 $150,000")
- 进度条显示当前完成百分比
- 支持添加多个目标, 设置目标日期

#### 持仓管理

**添加持仓**:
1. 点击 **Add Position**
2. 填写: Ticker, 数量, 成本价, 入场日期, 行业
3. (可选) 填写论点 (Thesis): 预期收益、预期持有天数、目标价、止损价
4. 确认添加

**平仓**:
1. 在持仓表格中点击对应持仓的 **Close** 按钮
2. 输入: 退出价格、退出原因 (target_hit / stop_loss / thesis_invalid / other)
3. 系统自动计算实现盈亏并记录

**移除持仓**: 点击 **Remove** (不记录盈亏, 直接删除)

#### 配置图

- **Allocation Chart**: 切换 Ticker 或 Sector 视图
- **Sector Drill-Down**: 点击行业查看该行业下所有持仓

#### 批量导入

1. 点击 **Import CSV**
2. 上传 CSV 文件 (格式: ticker, quantity, avg_cost, entry_date, sector)
3. 系统自动跳过重复标的

#### 多组合支持

- **Profile Switcher**: 在页面顶部切换不同投资组合
- 支持创建、编辑、删除组合 Profile
- 每个 Profile 有独立的持仓和现金余额

---

### 4.4 Position Detail 持仓详情

**路由**: `/portfolio/:ticker`

查看单个持仓的详细信息。

#### 展示内容

| 区域 | 内容 |
|------|------|
| **面包屑导航** | Portfolio > AAPL |
| **状态徽章** | Open (绿) 或 Closed (灰) |
| **核心指标** | 入场价 / 当前价 / 盈亏 $ / 收益率 % |
| **Thesis Panel** | 投资论点 + 预期 vs 实际对比 |
| **Price History Chart** | 价格走势 + 入场线 + 目标线 + 止损线 |
| **P&L Timeline** | 盈亏时间线图表 |
| **Position Notes** | 快速备注 (随时添加文字记录) |
| **Dividend Tracker** | 股息记录 + 总股息 + 持有成本收益率 |
| **Position Timeline** | 从入场到退出的完整时间轴 |
| **Trade Annotations** | 交易教训/注释 (可打标签: entry_timing, position_sizing 等) |

#### 编辑论点

点击 **Edit Thesis** 可更新:
- 投资论述文本
- 目标价格
- 止损价格
- 预期持有天数
- 预期收益率

---

### 4.5 Watchlist 观察列表

**路由**: `/watchlist`

跟踪你感兴趣但尚未买入的标的。

#### 添加标的

**单个添加**:
1. 输入 Ticker + 资产类型
2. (可选) 设置目标买入价、警报价、备注
3. 点击 Add

**批量添加**:
1. 点击 **Bulk Add**
2. 粘贴多个 Ticker (每行一个或逗号分隔)
3. 确认添加

#### 信号过滤

顶部过滤栏: **ALL / BUY / SELL / HOLD / UNANALYZED**

点击后只显示对应信号的标的。

#### 操作功能

| 功能 | 说明 |
|------|------|
| **Analyze** | 对单个标的运行分析 |
| **Analyze All** | 批量分析所有观察标的 |
| **Compare Mode** | 选择 2-5 个标的进行并排对比 |
| **Alert Config** | 设置价格/信号变化告警 |
| **Edit** | 修改备注、目标价、警报价 |
| **Remove** | 从观察列表移除 |

#### 内联展开

点击某标的展开查看:
- 分析结果摘要
- 信号 + 置信度
- Agent 细分

---

### 4.6 Performance 业绩表现

**路由**: `/performance`

全面的投资业绩分析。

#### 顶部指标卡片

| 指标 | 说明 |
|------|------|
| Total P&L | 总已实现盈亏 |
| Win Rate | 胜率 (盈利交易 / 总交易) |
| Avg Win | 平均盈利百分比 |
| Avg Loss | 平均亏损百分比 |
| Total Trades | 总交易次数 |
| Alpha | 相对基准超额收益 |

#### 进阶指标

| 指标 | 说明 |
|------|------|
| Profit Factor | 盈利因子 (总盈利 / 总亏损) |
| Expectancy | 期望值 (每笔交易的平均预期收益) |
| Max Win Streak | 最长连续盈利次数 |
| Max Loss Streak | 最长连续亏损次数 |

#### 图表

| 图表 | 说明 |
|------|------|
| **Portfolio Value** | 90 天组合价值走势 (含投入成本虚线) |
| **Benchmark Comparison** | 对比 SPY 基准表现 (指数化到 100) |
| **Cumulative P&L** | 累计已实现盈亏曲线 |
| **Drawdown** | 回撤图 (面积图) |
| **Rolling Sharpe** | 滚动 Sharpe 比率 |
| **Monthly Heatmap** | 月度收益热力图 (年 x 月矩阵) |
| **Monthly Returns** | 月度收益柱状图 |
| **Top Performers** | 最佳 5 + 最差 5 笔交易 |
| **P&L Attribution** | 每个持仓对总收益的贡献百分比 |
| **Sector Performance** | 按行业汇总盈亏 |
| **Snapshot Comparison** | 对比两个日期的组合快照 |

---

### 4.7 Risk 风险管理

**路由**: `/risk`

专注于风险评估与压力测试。

#### 风险状态横幅

页面顶部显示整体风险等级:
- **LOW RISK** (绿色): 最大回撤 < 10%
- **MODERATE** (黄色): 最大回撤 10%-20%
- **HIGH RISK** (红色): 最大回撤 > 20%

#### 核心风险指标 (8 张卡片)

| 第一行 | 说明 |
|--------|------|
| Annualized Volatility | 年化波动率 |
| Sharpe Ratio | 夏普比率 (风险调整收益) |
| Max Drawdown | 历史最大回撤 |
| Current Drawdown | 当前回撤 |

| 第二行 | 说明 |
|--------|------|
| VaR (95%) | 在险价值 (95% 置信) |
| CVaR (95%) | 条件在险价值 |
| Best Day | 历史最佳单日表现 |
| Worst Day | 历史最差单日表现 |

#### Portfolio Health Score (健康评分)

综合评分 (0-100), 由 4 个子维度组成:

| 子维度 | 评估内容 |
|--------|----------|
| Diversification | 分散化程度 (持仓数、行业数) |
| Risk | 风险水平 (波动率、回撤) |
| Thesis Adherence | 论点执行度 (有论点的持仓占比) |
| Momentum | 动量评分 (盈利持仓占比) |

#### 高级分析

| 功能 | 说明 |
|------|------|
| **Correlation Matrix** | 持仓间相关性矩阵 + 热力图 |
| **Concentration Risk** | 集中度风险等级 (HIGH / MODERATE / LOW) |
| **Stress Test** | 预设场景压力测试 (2008 金融危机, COVID Crash 等) |
| **Monte Carlo Simulation** | 蒙特卡洛模拟 (30 天前瞻, 1000 次模拟) |
| **Drawdown Chart** | 90 天回撤走势图 |

---

### 4.8 Journal 交易日志

**路由**: `/journal`

复盘已完成的交易, 从中学习。

#### 绩效概览 (4 张卡片)

Total Trades / Win Rate / Avg Hold Days / Total Realized P&L

#### Trading Insights (交易洞察)

系统自动从已平仓数据中提炼洞察:
- **positive** (绿): 表现良好的模式 (如 "胜率 60% 高于基准")
- **neutral** (蓝): 中性观察 (如 "平均持有 25 天在目标范围内")
- **negative** (红): 需要关注的问题

#### 收益分布图

直方图展示所有已平仓交易的收益分布 (8 个区间: < -20% 到 > 20%)

#### 累计盈亏曲线

面积图展示已实现盈亏的累计走势

#### Lesson Summary (教训总结)

查看所有交易注释中的教训标签汇总

#### Lesson Tag Analytics (教训标签分析)

| 指标 | 说明 |
|------|------|
| Tag | 教训标签 (如 Entry Timing, Position Sizing) |
| Count | 出现次数 |
| Win Rate | 该标签对应交易的胜率 |
| Avg Return | 该标签对应交易的平均收益 |

**Pattern Alert**: 低胜率标签 (< 40%) 会显示黄色警告: "consider reviewing this pattern"

#### 已平仓表格

展开每行可查看:
- 完整投资论点
- 预期 vs 实际收益对比
- 持有天数对比
- 交易注释 (可添加新注释 + 教训标签)

---

### 4.9 Backtest 回测

**路由**: `/backtest`

基于历史数据验证交易策略。

#### 单一回测

1. 填写参数:
   - Ticker + 资产类型
   - 日期范围 (Start / End)
   - 初始资金
   - 再平衡频率 (Daily / Weekly / Monthly)
   - 仓位大小 (% of capital)
   - 止损 % / 止盈 %
   - 选择 Agent 组合
2. 点击 **Run Backtest**
3. 查看结果: 收益曲线、交易列表、性能指标

#### 回测指标

Sharpe / Sortino / Max Drawdown / Calmar / Win Rate / Profit Factor / CAGR / Total Trades

#### 批量回测

- 输入多个 Ticker
- 选择多组 Agent 组合
- 生成交叉对比矩阵

#### Preset Manager (预设管理)

- 保存常用回测参数为预设
- 一键加载预设运行回测

#### 历史对比

- 保存回测结果 (命名保存)
- 从历史列表中选择 2+ 次回测进行对比
- 并排展示收益曲线和指标

---

### 4.10 Signals 信号追踪

**路由**: `/signals`

追踪和评估分析信号的质量。

#### 7 个标签页

| 标签 | 内容 |
|------|------|
| **History** | 信号历史表格 (可按 Ticker / Signal 过滤, 分页) |
| **Accuracy** | 信号准确率统计 (命中率、精确度) |
| **Calibration** | 置信度校准图 (信号置信度 vs 实际表现) |
| **Agent Perf** | 各 Agent 的独立准确率/召回率 |
| **Accuracy Trend** | 准确率时间趋势线图 |
| **Agreement** | Agent 间一致性热力图 |
| **Timeline** | 信号时间轴 (按市场状态着色) |

---

### 4.11 Monitoring 监控告警

**路由**: `/monitoring`

集中管理所有告警。

#### 告警看板

- **Summary Chips**: 按严重程度统计 (Critical / High / Warning / Low / Info)
- **Severity Filter**: 按严重程度筛选告警
- **Acknowledged Filter**: 筛选已确认/未确认告警
- **Batch Acknowledge**: 批量确认所有未确认告警

#### Alert Rules (告警规则)

自定义告警触发条件:

1. 点击 **Add Rule**
2. 设置规则参数:
   - Name: 规则名称
   - Metric: 指标 (drawdown_pct, volatility, price_drop 等)
   - Condition: 条件 (gt / lt / eq)
   - Threshold: 阈值
   - Severity: 严重程度
3. 规则可启用/禁用, 也可删除

#### 其他功能

| 功能 | 说明 |
|------|------|
| **Monitor Check** | 手动触发一次健康检查 |
| **Alert Timeline** | 告警时间轴图表 |
| **Alert Analytics** | 告警统计分析 |

---

### 4.12 Weights 权重分布

**路由**: `/weights`

查看当前分析系统的权重配置。

#### 两类权重

| 类型 | 说明 |
|------|------|
| **Agent Weights** | FundamentalAgent / TechnicalAgent / MacroAgent 的权重分配 |
| **Factor Weights** | momentum_trend / market_structure / volatility_risk / macro_correlation / cycle_timing / liquidity_volume / network_adoption |

以甜甜圈图展示, 配有详细图例和百分比。

---

### 4.13 Daemon 后台任务

**路由**: `/daemon`

管理自动化后台监控任务。

#### 5 个预设任务

| 任务 | 频率 | 说明 |
|------|------|------|
| Daily Check | 工作日 17:00 ET | 获取价格, 检查止损/目标/论点偏移, 生成告警 |
| Weekly Revaluation | 周六 10:00 ET | 对所有持仓重新运行完整分析 |
| Catalyst Scan | 按需 | 新闻/催化剂扫描 (需 Anthropic Key) |
| Regime Detection | 按需 | 市场状态检测 (需 FRED Key) |
| Watchlist Scan | 按需 | 扫描观察列表中的价格和信号变化 |

#### 操作

- **Run Once**: 手动触发单次运行
- **Status**: 查看每个任务的状态 (Running / Completed / Failed / Idle)
- **Run History**: 查看历史运行记录 (时间、时长、状态)

---

### 4.14 Analysis History 分析历史

**路由**: `/analysis-history`

浏览所有历史分析记录。

- 按 Ticker 和 Signal 过滤
- 表格显示: Ticker / 分析日期 / Signal / 置信度 / 最终评分 / 市场状态
- 展开行查看完整分析详情
- 默认显示最近 20 条

---

### 4.15 Settings 系统设置

**路由**: `/settings`

#### Appearance (外观)

- **Dark**: 深色主题
- **Light**: 浅色主题
- **System**: 跟随系统偏好

#### Notifications (通知)

- Email / Telegram 通道开关
- Send Test Email / Send Test Telegram 按钮

#### Notification Configuration (通知配置)

- SMTP 服务器配置 (Host, Port, User, Password)
- Telegram Bot Token / Chat ID
- Alert Severity Filters: 选择哪些严重级别触发通知 (Critical / High / Warning / Info)

#### Data & Cache (数据与缓存)

- **Cache TTL**: 选择缓存时长 (15s / 30s / 60s / 2min / 5min)
- **Clear Cache**: 一键清除所有缓存数据

#### Export Hub (导出中心)

7 种导出, 5 个分类:

| 分类 | 导出项 | 格式 |
|------|--------|------|
| Portfolio | Portfolio CSV | CSV |
| Portfolio | Trade Journal CSV | CSV |
| Portfolio | Full Report | JSON |
| Performance | Performance CSV | CSV |
| Risk | Risk CSV | CSV |
| Signals | All Signals CSV | CSV |
| Alerts | Alerts CSV | CSV |

#### System Info (系统信息)

显示: 系统状态、数据库路径、版本号、持仓数量、信号数量、告警数量

#### Configuration (配置指引)

显示如何配置环境变量和 API Key

---

## 5. CLI 命令行操作

除了 Web 界面, 所有核心功能也可通过命令行使用。

### 5.1 分析标的

```bash
# 标准分析
python -m cli.analyze_cli AAPL

# 详细分析 (含所有指标和权重计算过程)
python -m cli.analyze_cli AAPL --detail

# 加密货币
python -m cli.analyze_cli BTC --asset-type btc

# JSON 输出
python -m cli.analyze_cli MSFT --json
```

### 5.2 投资组合管理

```bash
# 添加持仓
python -m cli.portfolio_cli add --ticker AAPL --qty 100 --cost 185.50 --date 2026-01-15 --asset-type stock --sector Technology

# 查看组合
python -m cli.portfolio_cli show

# 设置现金
python -m cli.portfolio_cli set-cash --amount 200000

# 移除持仓
python -m cli.portfolio_cli remove --ticker AAPL

# 股票拆分 (如 4:1)
python -m cli.portfolio_cli split --ticker AAPL --ratio 4

# 组合缩放 (如 0.1x 模拟盘)
python -m cli.portfolio_cli scale --multiplier 0.1
```

### 5.3 监控与告警

```bash
# 运行健康检查
python -m cli.monitor_cli check

# 查看告警
python -m cli.monitor_cli alerts

# 按 Ticker 过滤
python -m cli.monitor_cli alerts --ticker AAPL

# 按严重程度过滤
python -m cli.monitor_cli alerts --severity CRITICAL
```

### 5.4 信号追踪

```bash
# 信号历史
python -m cli.signal_cli history
python -m cli.signal_cli history --ticker AAPL --signal BUY

# 准确率统计
python -m cli.signal_cli stats

# 置信度校准
python -m cli.signal_cli calibration

# Agent 表现
python -m cli.signal_cli agents
```

### 5.5 回测

```bash
# 基础回测
python -m cli.backtest_cli run AAPL --start 2024-01-01 --end 2025-12-31

# 自定义参数
python -m cli.backtest_cli run AAPL \
  --start 2024-01-01 --end 2025-12-31 \
  --agents technical,fundamental \
  --frequency weekly \
  --capital 100000 \
  --stop-loss 0.10 \
  --take-profit 0.20
```

### 5.6 图表生成

```bash
# 价格 + 技术指标图 (在浏览器中打开)
python -m cli.charts_cli analysis AAPL

# 组合配置图
python -m cli.charts_cli portfolio

# 置信度校准图
python -m cli.charts_cli calibration

# 预期 vs 实际漂移图
python -m cli.charts_cli drift
```

### 5.7 后台守护进程

```bash
# 启动 (默认: 工作日 17:00, 周六 10:00)
python -m cli.daemon_cli start

# 自定义时间
python -m cli.daemon_cli start --daily-hour 16 --weekly-day sun --timezone US/Pacific

# 单次运行
python -m cli.daemon_cli run-once daily

# 查看状态
python -m cli.daemon_cli status
```

---

## 6. 多智能体分析系统

系统的核心是 6 个专业 Agent 并行分析, 各自独立给出信号后加权汇总。

### 6.1 Agent 清单

| Agent | 类型 | 指标数 | 数据源 | 需要 API Key |
|-------|------|--------|--------|-------------|
| **TechnicalAgent** | 规则型 | 17 | yfinance | 否 |
| **FundamentalAgent** | 规则型 | 20 | yfinance | 否 |
| **MacroAgent** | 规则型 | 11 | FRED | FRED_API_KEY |
| **CryptoAgent** | 规则型 | 7 | yfinance/ccxt | 否 |
| **SentimentAgent** | LLM | - | 新闻 + Claude | ANTHROPIC_API_KEY |
| **SummaryAgent** | LLM | - | 组合数据 + Claude | ANTHROPIC_API_KEY |

### 6.2 Agent 详情

**TechnicalAgent (技术分析)**
- SMA (20/50/200), RSI, MACD, Bollinger Bands, ADX
- 成交量分析, 趋势强度, 波动率评估
- 自动适配股票和加密货币

**FundamentalAgent (基本面分析)**
- P/E, PEG, ROE, 收入增长率, 负债率
- 股息率, 盈利增长, 现金流
- 仅适用于股票 (非加密货币)

**MacroAgent (宏观分析)**
- VIX 指数, 收益率曲线, 失业率
- M2 货币供应量, CLI 综合领先指标
- 联邦基金利率, 信用利差

**CryptoAgent (加密货币专用)**
- 7 因子模型: 动量、波动率状态、趋势、成交量
- 回撤分析、均值回归、动量趋势
- 仅用于 BTC/ETH

### 6.3 信号生成过程

```
输入: Ticker + Asset Type
  |
  v
[Regime Detector] -> 市场状态 (Bull/Bear/Sideways/HighVol/RiskOff)
  |
  v
[Agent 1-6 并行分析] -> 各自的 Signal + Confidence + Metrics
  |
  v
[Signal Aggregator] -> 加权汇总 (考虑市场状态调整权重)
  |
  v
输出: Final Signal (BUY/HOLD/SELL) + Confidence % + Warnings
```

### 6.4 信号解读

| 信号 | 置信度 | 建议 |
|------|--------|------|
| BUY | > 65% | 考虑建仓或加仓 |
| BUY | 50-65% | 弱信号, 等待确认 |
| HOLD | any | 保持现有仓位 |
| SELL | > 65% | 考虑减仓或清仓 |
| SELL | 50-65% | 弱信号, 密切关注 |

**低共识警告**: 如果 Agent 间信号分歧大, 系统会显示低共识警告, 建议谨慎。

---

## 7. 告警与通知

### 7.1 告警类型

| 告警类型 | 严重程度 | 触发条件 |
|----------|---------|----------|
| STOP_LOSS_HIT | CRITICAL | 价格跌破止损价 |
| TARGET_HIT | INFO | 价格触及目标价 |
| TIME_OVERRUN | WARNING | 持有天数超过预期 |
| SIGNIFICANT_LOSS | HIGH | 亏损超过 15% |
| SIGNIFICANT_GAIN | INFO | 盈利超过 25% |
| PRICE_DROP | HIGH | 单日大幅下跌 |
| VOLUME_SPIKE | WARNING | 成交量异常放大 |
| SIGNAL_REVERSAL | HIGH | 信号从 BUY 翻转为 SELL (或反之) |
| THESIS_DRIFT | WARNING | 价格偏离论点预期超过 10% |

### 7.2 通知渠道

**邮件 (SMTP)**:
1. 在 Settings > Notification Configuration 中配置 SMTP
2. 支持 Gmail, Outlook, 自定义 SMTP 服务器
3. HTML 格式告警邮件

**Telegram**:
1. 创建 Telegram Bot (通过 @BotFather)
2. 获取 Bot Token 和 Chat ID
3. 在 Settings 中配置

**Web 告警**:
- 无需配置, 始终可用
- Dashboard 和 Monitoring 页面实时显示

### 7.3 告警管理

- **Acknowledge**: 确认已查看 (不删除)
- **Delete**: 永久删除告警
- **Batch Acknowledge**: 批量确认
- **Filter**: 按严重程度、确认状态、Ticker 过滤

---

## 8. 数据导出

### 8.1 Web 界面导出

在 Settings > Export Hub 页面, 点击下载:

| 文件 | 内容 |
|------|------|
| `portfolio.csv` | 当前所有持仓 (ticker, qty, cost, value, P&L) |
| `trades.csv` | 已平仓记录 (entry, exit, return, hold days) |
| `report.json` | 完整组合报告 (持仓 + 指标 + 摘要) |
| `performance.csv` | 绩效概要数据 |
| `risk.csv` | 风险指标快照 |
| `signals.csv` | 信号历史记录 |
| `alerts.csv` | 告警历史记录 |

### 8.2 API 导出端点

直接通过 API 下载:

```
GET /api/export/portfolio/csv
GET /api/export/trades/csv
GET /api/export/portfolio/report
GET /api/export/signals/csv?ticker=AAPL&limit=100
GET /api/export/alerts/csv?limit=100
GET /api/export/performance/csv
GET /api/export/risk/csv?days=90
```

---

## 9. 日常使用建议

### 9.1 推荐日常流程

| 时间 | 操作 | 位置 |
|------|------|------|
| 早上 | 查看 Dashboard, 浏览告警和今日变动 | Dashboard |
| 早上 | 查看 Earnings Calendar, 关注近期财报 | Dashboard |
| 交易前 | 对目标标的运行分析 | Analysis 页面 |
| 交易前 | 查看 Watchlist 中接近目标价的标的 | Watchlist |
| 交易后 | 更新持仓 (添加/平仓/更新现金) | Portfolio |
| 交易后 | 为平仓交易添加注释和教训标签 | Journal |
| 每周 | 查看信号准确率趋势 | Signals |
| 每周 | 检查风险指标和相关性 | Risk |
| 每月 | 复盘业绩和月度收益 | Performance |
| 每月 | 运行回测验证策略 | Backtest |

### 9.2 新用户快速上手

1. **设置现金余额**: Portfolio > 设置初始现金
2. **添加持仓**: Portfolio > Add Position (至少 2-3 个标的)
3. **填写论点**: 为每个持仓添加目标价和止损价
4. **分析一个标的**: Analysis > 输入感兴趣的 Ticker
5. **设置观察列表**: Watchlist > 添加 3-5 个感兴趣的标的
6. **配置通知**: Settings > 配置邮件或 Telegram
7. **启动守护进程**: Daemon > 让系统自动监控

### 9.3 最佳实践

- **始终设置止损**: 每个持仓都应有止损价, 让系统在触发时告警
- **记录投资论点**: 入场时写下为什么买入, 方便日后复盘
- **定期复盘**: 每周查看 Journal, 从已平仓交易中学习
- **关注教训标签**: Lesson Tag Analytics 帮助发现反复犯的错误
- **不要忽视告警**: CRITICAL 告警需要立即处理
- **使用回测验证**: 在实际交易前, 用回测确认策略在历史数据上有效

---

## 10. API 端点参考

### 10.1 端点分类汇总

| 分类 | 端点数 | 说明 |
|------|--------|------|
| 系统健康 | 2 | `/health`, `/system/info` |
| 分析 | 6 | 单标的分析、催化剂、相关性、价格历史、仓位大小 |
| 投资组合 | 15 | 持仓 CRUD、历史、现金、缩放、拆分、论点、目标 |
| 股息/财报 | 3 | 股息记录、未来财报 |
| 多组合 | 6 | Profile CRUD + 切换 |
| 信号 | 6 | 信号历史、准确率、校准、Agent 表现、趋势 |
| 回测 | 2 | 单次 + 批量回测 |
| 监控告警 | 12 | 告警 CRUD、规则引擎、统计、时间线 |
| 分析统计 | 16 | 价值历史、绩效、风险、相关性、基准对比等 |
| 守护进程 | 3 | 状态、手动运行、历史 |
| 分析历史 | 2 | 分页查询、已分析标的列表 |
| 数据导出 | 7 | CSV/JSON 导出 |
| 交易日志 | 6 | 注释、快速笔记、教训统计、洞察 |
| 观察列表 | 11 | CRUD、批量添加、分析、警报配置 |
| 状态检测 | 2 | 当前状态、历史 |
| 风险/压力 | 3 | 压力测试、蒙特卡洛、健康评分 |
| 摘要 | 2 | AI 生成摘要、最新摘要 |
| 通知 | 2 | 配置 CRUD |
| 权重 | 1 | 当前权重 |

**总计约 100 个端点**

### 10.2 通用响应格式

成功响应:
```json
{
  "data": { ... },
  "warnings": ["optional warning message"]
}
```

错误响应:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "detail": null
  }
}
```

### 10.3 交互式 API 文档

启动后端后访问 http://localhost:8000/docs 可使用 Swagger UI 测试所有端点。

---

## 11. 常见问题

### Q: 系统不需要任何 API Key 就能用吗?

**A**: 是的。系统的核心功能 (技术分析、基本面分析、投资组合管理、回测) 完全不需要 API Key。FRED Key 增加宏观分析, Anthropic Key 增加情绪分析和 AI 摘要, 但都是可选的。

### Q: 支持做空吗?

**A**: 当前版本仅支持做多 (Long)。做空支持计划在未来版本中添加。

### Q: 数据存储在哪里?

**A**: 所有数据存储在本地 SQLite 文件 `data/investment_agent.db`。无需外部数据库, 数据完全本地化。

### Q: 分析需要多长时间?

**A**: 单标的分析通常 3-10 秒 (取决于网络和启用的 Agent 数量)。批量分析按标的数线性增长。

### Q: 如何备份数据?

**A**: 复制 `data/investment_agent.db` 文件即可。建议定期备份。也可使用 Export Hub 导出 CSV 作为额外备份。

### Q: 回测结果可靠吗?

**A**: TechnicalAgent 的回测使用严格的 Walk-forward 方法, 无前视偏差, 结果可靠。FundamentalAgent 回测因 yfinance 数据非 Point-in-Time, 结果会标注 non-PIT 免责声明。

### Q: 前端和后端可以分开部署吗?

**A**: 可以。前端通过环境变量指向后端 API 地址。修改 `frontend/src/lib/api.ts` 中的 baseURL 即可。

### Q: 如何重置所有数据?

**A**: 删除 `data/investment_agent.db` 文件, 重启后端, 数据库会自动重新初始化。

### Q: 支持哪些浏览器?

**A**: 支持所有现代浏览器 (Chrome, Firefox, Safari, Edge)。推荐使用 Chrome 以获得最佳体验。

---

## 附录: 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+K` / `Cmd+K` | 打开命令面板 (快速跳转页面) |

---

## 附录: 告警严重程度说明

| 级别 | 颜色 | 含义 | 建议动作 |
|------|------|------|----------|
| CRITICAL | 红色 | 需要立即处理 | 马上查看, 可能需要平仓 |
| HIGH | 橙色 | 重要但不紧急 | 当天内查看并评估 |
| WARNING | 黄色 | 值得关注 | 下次交易时考虑 |
| LOW | 蓝色 | 低优先级提醒 | 知晓即可 |
| INFO | 灰色 | 信息性通知 | 参考信息 |

---

## 附录: 市场状态 (Regime) 说明

| 状态 | 说明 | 对分析的影响 |
|------|------|-------------|
| BULL | 牛市 | 提高做多信号权重 |
| BEAR | 熊市 | 提高做空/防御信号权重 |
| SIDEWAYS | 震荡 | 降低趋势信号权重 |
| HIGH_VOL | 高波动 | 增加风险因子权重 |
| RISK_OFF | 避险 | 偏向防御性资产 |

---

*本手册基于 Investment Agent v5 Sprint 38 版本编写。如有功能更新, 请参考项目 README 和 Architecture 文档获取最新信息。*
