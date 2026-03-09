# Task 002: Expected vs Actual 偏差追踪引擎核心逻辑 (Drift Analyzer)

## 🎯 任务目标 (Goal)
基于 Task 001 建立的底层数据库，构建**Drift Analysis Engine (预期vs实际偏差分析器)**。这是整个“会成长的智能系统”中最关键的一环，用于评估系统到底有没有用，有没有盲目自信。

## 📥 输入上下文 (Context)
- 数据库表 `positions_thesis` (保存预期的自信心、预期入场价、预期回报等)。
- 数据库表 `trade_executions` (保存实际买入卖出的价格和数量)。
- 你的架构文档在 `docs/architecture_v4.md` (请参考第 5 节 `Expected vs Actual ROI Tracking`)。

## 🛠️ 具体需求 (Requirements)

1. **新建 `engine/drift_analyzer.py`**:
   - 编写异步类 `DriftAnalyzer`，需传入 `aiosqlite.Connection` 或数据库路径进行初始化。
   - 编写方法 `compute_position_drift(thesis_id: int) -> dict`:
     - 给定一个 `thesis_id`，查询其预期的目标。
     - 查询所有关联的 `trade_executions`。
     - **计算指标 1: Entry Drift (入场偏差)** -> `(实际加权平均建仓价 - 预期建仓价) / 预期建仓价`。
     - **计算指标 2: Return Drift (回报偏差)** -> 如果仓位已平（或计算未实现浮盈），计算 `实际收益率 - 预期收益率`。
   - 返回一个字典，包含计算好的这几个偏差值。

2. **核心业务逻辑边界 (Edge Cases to Handle)**:
   - 必须处理分批建仓 (Scaling in)：如果 `trade_executions` 里面有多次 'BUY' 操作，必须计算它们的加权平均建仓成本（Weighted Average Entry Price）。
   - 如果没有相关的执行记录，直接抛出或者返回包含 `None` 的提示。

3. **创建测试脚本 `tests/test_002_drift.py`**:
   - 初始化一个基于内存（或者测试文件）的 SQLite，先通过 `database.py` 创建表结构。
   - 插入 1 条 `thesis`（预期建仓 $100，预期回报 10%）。
   - 插入 2 条 `trade_executions` 的分批 BUY（一次 $102 买 100股，一次 $104 买 100股）。
   - 调用 `DriftAnalyzer` 的方法，断言加权平均成本是 $103，Entry Drift 是 `(103-100)/100 = 3%`。

## ✅ 验收标准 (Acceptance Criteria)
- 代码无报错，遵循 PEP 8，有 Type Hints。
- 加权平均成本计算（VWAP）的逻辑完全正确。
- 测试必须成功通过。
- **强制要求**：在完成代码并跑通测试后，必须在 `docs/AGENT_SYNC.md` 追加你的开发总结，按照 `docs/DEVELOPER_INSTRUCTIONS.md` 的格式。