# Task 001: 核心数据模型与 SQLite WAL 并发基础

## 🎯 任务目标 (Goal)
搭建系统的基石：创建支持并发高频写入的 SQLite 数据库，并实现 `trade_records` (Expected vs Actual 追踪) 和 `portfolio_snapshots` 等核心表结构。
> **⚠️ 关键架构约束 (Architectural Constraint):** 
> 必须使用 `aiosqlite` 并在连接初始化时强制启用 WAL（Write-Ahead Logging）模式：`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`。否则系统后续运行 Monitoring Daemon 时会因为高并发产生 `database is locked` 报错。

## 📥 输入上下文 (Context)
- 我们正在开发 Investment Analysis Agent v4。
- 后续将有 FastAPI 供前端读取数据，同时后台会有 APScheduler 守护进程每隔 4 小时扫描催化剂、每天收盘计算持仓快照（Snapshot）。
- Drift 分析引擎需要区分预期建仓逻辑（Expected）与真实交易执行（Actual）。

## 🛠️ 具体需求 (Requirements)

1. **新建 `db/database.py`**:
   - 编写 `init_db()` 异步函数，负责创建数据库文件 `data/investment_agent.db`。
   - 必须配置 WAL 模式。

2. **核心表结构定义 (Schema)**:
   - `positions_thesis` (父表): 记录系统发出建仓建议时的预期。
     - 字段: `id`, `ticker`, `asset_type`, `expected_signal`, `expected_confidence`, `expected_entry_price`, `expected_target_price`, `expected_stop_loss`, `expected_hold_days`, `created_at`
   - `trade_executions` (子表): 记录真实的买卖操作（支持分批建仓/平仓）。
     - 字段: `id`, `thesis_id` (FK), `action` ('BUY', 'SELL'), `quantity`, `executed_price`, `executed_at`, `reason` ('manual', 'target_hit', 'stop_loss')
   - `portfolio_snapshots`: 记录账户全局状态。
     - 字段: `id`, `timestamp`, `total_value`, `cash`, `positions_json` (记录当时的持仓快照，存为 JSON 字符串), `trigger_event`

3. **创建测试脚本 `tests/test_001_db.py`**:
   - 编写一个异步测试脚本，模拟插入一条 `positions_thesis` 记录和两条对应的 `trade_executions` 记录，然后读取出来验证。

## ✅ 验收标准 (Acceptance Criteria)
- 代码无任何语法错误，且遵循 PEP 8（使用 type hints）。
- 运行 `pytest tests/test_001_db.py` (或直接执行该脚本) 必须成功通过。
- `aiosqlite` 成功执行 WAL PRAGMA，不出现并发锁死警告。

---
**给 Codex 的指令 (Instruction for Codex):**
请读取以上要求，一次性输出并创建所需的 Python 文件目录结构及代码。写完后请运行测试脚本。如果报错，请自行修复直至测试通过。完成所有工作后，请提交一个 git commit。