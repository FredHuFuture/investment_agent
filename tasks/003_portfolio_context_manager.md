# Task 003: Portfolio Context Manager (持仓管理 + Exposure 计算)

## 🎯 任务目标 (Goal)
构建**活跃持仓跟踪层**——数据模型、CRUD 操作、持仓暴露度计算、SQLite 持久化、CLI 接口。这是 v4 架构的核心新增能力：让系统从 stateless 的"问一次答一次"进化为有记忆的持仓管理系统。

## 📥 输入上下文 (Context)
- 数据库基础已在 Task 001 中搭好（`db/database.py`，WAL 模式，aiosqlite）。
- 架构设计参考 `docs/architecture_v4.md` 第 4 节 `Portfolio Context Manager`。
- 已知边缘案例参考 `project/investment_agent_v4_review.md` 第 3 节 `Portfolio Edge Cases`。
- **本任务不依赖外部数据源**——`current_price` 在本任务中默认为 0（将在 Task 004 DataProvider 完成后接入实时价格刷新）。

## 🛠️ 具体需求 (Requirements)

### 1. 扩展数据库 Schema (`db/database.py`)

在 `init_db()` 中新增两个表：

```sql
-- 活跃持仓表（区别于 positions_thesis 分析记录表）
CREATE TABLE IF NOT EXISTS active_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,  -- 每个 ticker 只能有一条活跃记录
    asset_type TEXT NOT NULL CHECK (asset_type IN ('stock', 'btc', 'eth')),
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL,
    sector TEXT,            -- GICS sector (stocks only), e.g. 'Technology'
    industry TEXT,          -- GICS industry (stocks only)
    entry_date TEXT NOT NULL,  -- ISO format: '2026-02-10'
    original_analysis_id INTEGER,  -- FK to positions_thesis (nullable)
    expected_return_pct REAL,      -- 建仓时系统预期回报 (nullable)
    expected_hold_days INTEGER,    -- 建仓时系统建议持有天数 (nullable)
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (original_analysis_id) REFERENCES positions_thesis(id)
);

-- 组合元数据表（存放 cash 等全局状态）
CREATE TABLE IF NOT EXISTS portfolio_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

新增索引：
```sql
CREATE INDEX IF NOT EXISTS idx_active_positions_ticker ON active_positions(ticker);
CREATE INDEX IF NOT EXISTS idx_active_positions_asset_type ON active_positions(asset_type);
```

### 2. 数据模型 (`portfolio/models.py`)

新建 `portfolio/` 目录，创建 `__init__.py` 和 `models.py`。

**Position dataclass:**
```python
@dataclass
class Position:
    ticker: str
    asset_type: str            # 'stock' | 'btc' | 'eth'
    quantity: float
    avg_cost: float
    current_price: float = 0.0  # 默认 0, Task 004 后接入实时价格
    sector: str | None = None
    industry: str | None = None
    entry_date: str = ""        # ISO format
    original_analysis_id: int | None = None
    expected_return_pct: float | None = None
    expected_hold_days: int | None = None

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.quantity * self.avg_cost

    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis

    @property
    def holding_days(self) -> int:
        """从 entry_date 到今天的天数。"""
        # 用 date.fromisoformat 解析 entry_date
        ...

    @classmethod
    def from_db_row(cls, row: tuple) -> "Position": ...

    def to_dict(self) -> dict: ...
```

**Portfolio dataclass:**
```python
@dataclass
class Portfolio:
    positions: list[Position]
    cash: float
    total_value: float                          # sum(market_values) + cash
    stock_exposure_pct: float                   # 美股占比
    crypto_exposure_pct: float                  # Crypto 占比
    cash_pct: float
    sector_breakdown: dict[str, float]          # {"Technology": 0.35, ...}
    top_concentration: list[tuple[str, float]]  # [("MSFT", 0.22), ...]

    def to_dict(self) -> dict: ...
```

### 3. PortfolioManager 类 (`portfolio/manager.py`)

```python
class PortfolioManager:
    def __init__(self, db: str | Path | aiosqlite.Connection): ...

    # === CRUD ===
    async def add_position(
        self, ticker: str, asset_type: str, quantity: float,
        avg_cost: float, entry_date: str,
        sector: str | None = None, industry: str | None = None,
    ) -> int:
        """INSERT. 如果 ticker 已存在则抛出 ValueError。返回新记录 ID。"""

    async def remove_position(self, ticker: str) -> bool:
        """DELETE by ticker. 返回是否成功删除。"""

    async def update_position(self, ticker: str, **kwargs) -> bool:
        """UPDATE 指定字段。自动更新 updated_at。
        允许更新的字段: quantity, avg_cost, sector, industry, entry_date,
        expected_return_pct, expected_hold_days。"""

    async def get_position(self, ticker: str) -> Position | None: ...
    async def get_all_positions(self) -> list[Position]: ...

    # === Cash 管理 ===
    async def set_cash(self, amount: float) -> None:
        """写入 portfolio_meta 表 key='cash'。"""

    async def get_cash(self) -> float:
        """读取 portfolio_meta 表。如果不存在返回 0.0。"""

    # === 批量操作 ===
    async def scale_portfolio(self, multiplier: float) -> int:
        """等比例缩放所有持仓的 quantity。返回受影响的行数。
        注意: 不修改 avg_cost（成本不因资金增减而变）。"""

    async def apply_split(self, ticker: str, ratio: int) -> bool:
        """拆股: quantity *= ratio, avg_cost /= ratio。
        返回是否成功。如果 ticker 不存在返回 False。"""

    # === Portfolio 加载与计算 ===
    async def load_portfolio(self) -> Portfolio:
        """加载所有持仓 + cash，计算以下聚合指标:
        - total_value = sum(position.market_value) + cash
          （注意: 因为 current_price 暂时为 0，total_value 在本 Task
          中 = cash。后续 Task 004 接入价格后才有真正的 total_value。
          但用 cost_basis 代替 market_value 作为临时估算也可以，
          标注清楚即可。）
        - stock_exposure_pct, crypto_exposure_pct, cash_pct
        - sector_breakdown
        - top_concentration (降序排列)
        """

    async def cash_reconciliation_check(self) -> str | None:
        """检查 stated cash vs implied cash (total_value - sum(market_values))。
        如果偏差 > 2% of total_value，返回警告消息。
        如果 total_value == 0 或持仓为空，返回 None (无需检查)。"""
```

**关键设计决策:**
- 因为 `current_price` 在本任务中无法刷新（没有 DataProvider），exposure 计算使用 **cost_basis** (`quantity * avg_cost`) 作为临时的 market_value 替代。在代码中用注释标注 `# TODO: replace with market_value when DataProvider is available`。
- `ticker` 字段在 `active_positions` 表中是 UNIQUE 的——同一个 ticker 不能有两条活跃持仓记录。如果需要加仓，应该调用 `update_position` 修改 quantity 和 avg_cost。

### 4. CLI 接口 (`cli/portfolio_cli.py`)

使用标准库 `argparse`，不引入额外依赖。

```bash
# 添加持仓
python -m cli.portfolio_cli add --ticker MSFT --qty 200 --cost 415.50 --date 2026-02-10 --asset-type stock --sector Technology

# 删除持仓
python -m cli.portfolio_cli remove --ticker MSFT

# 查看持仓 (ASCII 表格 + Exposure 摘要)
python -m cli.portfolio_cli show

# 设置现金
python -m cli.portfolio_cli set-cash --amount 150000

# 缩放
python -m cli.portfolio_cli scale --multiplier 2.0

# 拆股
python -m cli.portfolio_cli split --ticker AAPL --ratio 4
```

`show` 命令的输出格式:
```
═══════════════════════════════════════════════════════════════
 PORTFOLIO OVERVIEW
═══════════════════════════════════════════════════════════════
 Ticker   Type   Qty      Avg Cost    Cost Basis    Sector
 ──────   ────   ───      ────────    ──────────    ──────
 MSFT     stock  200      $415.50     $83,100       Technology
 AAPL     stock  100      $178.00     $17,800       Technology
 BTC      btc    0.50     $82,000     $41,000       —
 ──────────────────────────────────────────────────────────
 Total Cost Basis: $141,900
 Cash: $150,000
 Est. Total Value: $291,900

 EXPOSURE (by cost basis):
   US Stocks: 34.6%
   Crypto:    14.0%
   Cash:      51.4%

 SECTOR BREAKDOWN:
   Technology: 34.6%

 TOP CONCENTRATION:
   MSFT: 28.5%  |  BTC: 14.0%  |  AAPL: 6.1%
═══════════════════════════════════════════════════════════════
```

### 5. 测试 (`tests/test_003_portfolio.py`)

编写异步测试，使用临时 SQLite 数据库 (pytest `tmp_path`):

1. **test_add_and_load_positions**: 添加 3 个持仓 (MSFT stock, AAPL stock, BTC btc)，set cash $150,000，调用 `load_portfolio()`，验证:
   - positions 长度 = 3
   - cash = 150000
   - stock_exposure_pct + crypto_exposure_pct + cash_pct ≈ 1.0

2. **test_concentration_sorting**: 验证 `top_concentration` 按占比降序排列。

3. **test_sector_breakdown**: 两只 Technology 股票，验证 sector_breakdown["Technology"] = (MSFT_cost_basis + AAPL_cost_basis) / total_value。

4. **test_scale_portfolio**: 添加持仓后调用 `scale_portfolio(2.0)`，验证所有 quantity 翻倍，avg_cost 不变。

5. **test_apply_split**: 添加 AAPL qty=100, cost=$178。调用 `apply_split("AAPL", 4)`。验证 qty=400, avg_cost=$44.50。

6. **test_remove_position**: 添加后删除一个持仓，验证 `get_position` 返回 None，`load_portfolio` 中不再包含。

7. **test_duplicate_ticker_raises**: 尝试添加同一 ticker 两次，验证抛出 ValueError。

8. **test_cash_reconciliation_warning**: 设置 cash=$150,000，添加持仓使 total_value 可计算。手动将 portfolio_meta 的 cash 改为一个偏差值（如 $100,000），调用 `cash_reconciliation_check()`，验证返回非 None 的警告字符串。

## ✅ 验收标准 (Acceptance Criteria)
- `pytest tests/test_003_portfolio.py` 全部通过。
- `pytest tests/` 全部通过（不破坏已有的 test_001 和 test_002）。
- 代码遵循 PEP 8，使用 type hints。
- `portfolio/` 目录结构: `__init__.py`, `models.py`, `manager.py`。
- `cli/` 目录结构: `__init__.py`, `portfolio_cli.py`。
- 所有新建目录都有 `__init__.py`。

## ⚠️ 范围边界 (Out of Scope — 后续 Task 处理)
- `current_price` 实时刷新 → Task 004 (DataProvider)
- `beta_weighted`, `correlation_matrix` → 需要价格历史数据
- Portfolio-aware analysis overlay → Task 008
- ExitTriggers 字段 → Task 008
- Exposure 可视化 JSON 输出 → Task 009

---
**给 Developer Agent 的指令:**
请读取以上要求，一次性输出并创建所需的 Python 文件和目录结构。写完后请运行 `pytest tests/test_003_portfolio.py -v`。如果报错，请自行修复直至测试通过。然后运行 `pytest tests/ -v` 确保不破坏已有测试。完成后必须在 `docs/AGENT_SYNC.md` 追加汇报，然后执行 `git add .` 和 `git commit`。
