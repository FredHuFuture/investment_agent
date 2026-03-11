# Social Media Teaser -- Investment Analysis Agent

---

## 朋友圈 / 雪球 / 小红书 文案

### 版本 A (技术向 / 极客范)

> 周末写了个投资分析系统，4个AI Agent协作分析美股+BTC：
>
> - Technical Agent -- 17个技术指标 (RSI/MACD/布林带/SMA...)
> - Fundamental Agent -- 20个基本面指标 (PE/ROE/PEG/FCF...)
> - Macro Agent -- 宏观经济 (VIX/利率/M2/收益率曲线)
> - Crypto Agent -- 7因子模型 (市场结构/动量/波动/流动性/链上/周期...)
>
> 点击任意历史信号 = 右侧实时展开当时的完整分析。
> 置信度滑杆秒级过滤买卖信号。
> 全部离线运行，零API成本。
>
> Python + LangGraph + SQLite，162个测试全绿。
> 19个任务，13个模块，从0到1，一行代码没抄。
>
> 下一步：Claude API接入做催化剂扫描 + React前端。
>
> #投资 #量化 #AI #Python #开源

---

### 版本 B (产品向 / 大众友好)

> "你的投资日记会反驳你。"
>
> 做了一个投资分析系统：
> 给它一个股票代码，4个AI自动出报告 -- 技术面、基本面、宏观、加密货币各一个Agent。
>
> 最酷的功能：它会在历史K线上标出"当时应该买/卖"的信号，
> 点击任意一个 -> 右侧面板秒出完整分析：趋势得分、动量、RSI、MACD...
> 还能拖滑杆调节置信度阈值，实时过滤。
>
> 不联网也能跑。不花一分钱API费用。
> 纯本地 Python，162个自动化测试。
>
> 图1: AAPL分析 -- 点击卖出信号看右侧分析面板
> 图2: BTC 7因子分析 -- 市场结构/动量/波动/流动性/宏观/链上/周期
>
> #AI投资 #量化交易 #Python项目 #独立开发

---

### 版本 C (一句话钩子 + 雪球专用)

> 写了一套多Agent投资分析系统。
> 4个AI Agent + 7因子加密模型 + 历史信号回测 + 一键点击看分析。
> 美股BTC通吃，全离线零成本。
> 162个测试全通过，从第一行代码写到现在19个任务。
>
> 直接看图 ->

---

## 配图说明

**图1** (必选): AAPL价格分析 -- 展示完整界面
- 左侧: K线图 + SMA/布林带 + 买卖信号三角标记 + 成交量 + RSI
- 右侧: 点击SELL信号后的分析面板 (Sub-Scores, Indicators, Analysis)
- 顶部: 置信度滑杆 (30%) + 信号计数 (17 BUY + 9 SELL)
- 底部: Agent Signal Breakdown (Technical/Fundamental/Macro)
- **截图文件**: ss_37612rgax (AAPL with SELL detail)

**图2** (必选): BTC-USD 7因子分析 -- 展示加密货币独有功能
- 价格图: BTC $50K-$130K 两年走势 + 28 BUY + 15 SELL 信号
- 7因子图: Market Structure (+20), Momentum (-32), Volatility (-35), Liquidity (+15), Macro (0), Network (+35), Cycle (+5)
- **截图文件**: ss_9003xnbgt (BTC 7-factor)

**图3** (可选): 终端输出截图 -- 展示CLI分析报告
```
python -m cli.analyze_cli AAPL --detail
```

**图4** (可选): 项目架构图 or 代码结构截图

---

## Hashtag 建议

### 朋友圈
#投资分析 #AI #Python #量化 #独立开发

### 雪球
#投资分析系统 #量化投资 #AI选股 #技术分析 #BTC

### 小红书
#AI投资 #Python项目分享 #程序员副业 #独立开发者 #量化交易入门

### Twitter/X (English)
#OpenSource #InvestmentAI #Python #QuantFinance #MultiAgent
