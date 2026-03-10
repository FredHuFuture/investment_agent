# Task 004: 项目配置 + DataProvider 抽象层

## 🎯 任务目标 (Goal)
1. 建立正式的项目配置 (`pyproject.toml`)，统一管理依赖。
2. 构建 **DataProvider 抽象层** + 三个具体实现 (yfinance / ccxt / FRED)，使数据源可插拔替换。

## 📥 输入上下文 (Context)
- 架构设计参考 `docs/architecture_v4.md` 第 7 节 `Data Layer`，特别是 7.2 数据源矩阵和 7.4 Data Layer 抽象。
- 当前项目没有 `pyproject.toml` 或 `requirements.txt`，依赖全靠隐式安装。
- 后续的 Analysis Agents (Task 005-007) 将依赖此模块获取市场数据。
- **本任务与 Task 003 独立，可并行开发。**

## 🛠️ 具体需求 (Requirements)

### 1. 项目配置 (`pyproject.toml`)

在项目根目录创建：

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[project]
name = "investment-agent"
version = "0.1.0"
description = "Continuous portfolio monitoring and investment analysis agent"
requires-python = ">=3.11"
dependencies = [
    "aiosqlite>=0.19",
    "yfinance>=0.2",
    "ccxt>=4.0",
    "fredapi>=0.5",
    "pandas>=2.0",
    "pandas-ta>=0.3",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

> **注意**: `fredapi` 需要 FRED API key 才能实际调用。测试中使用 mock 即可。ccxt 不需要 API key 来获取公开市场数据。

### 2. 抽象基类 (`data_providers/base.py`)

```python
from abc import ABC, abstractmethod
import pandas as pd

class DataProvider(ABC):
    """
    数据源抽象接口。
    Phase 1: YFinanceProvider / CcxtProvider / FredProvider
    Phase 3: FMPProvider (implements same interface)
    """

    @abstractmethod
    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """返回 OHLCV DataFrame.
        columns: ['Open', 'High', 'Low', 'Close', 'Volume']
        index: DatetimeIndex
        """
        ...

    @abstractmethod
    async def get_current_price(self, ticker: str) -> float:
        """返回最新价格 (latest close 或 last trade price)。"""
        ...

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        """返回财务报表数据。
        默认实现抛出 NotImplementedError (crypto 无财报)。
        period: 'annual' | 'quarterly'
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support financials."
        )

    async def get_key_stats(self, ticker: str) -> dict:
        """返回关键统计指标。
        默认实现抛出 NotImplementedError。
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support key_stats."
        )

    @abstractmethod
    def is_point_in_time(self) -> bool:
        """回测引擎用此标记是否需要加 non-PIT disclaimer。"""
        ...

    @abstractmethod
    def supported_asset_types(self) -> list[str]:
        """返回此 provider 支持的资产类型列表。"""
        ...
```

### 3. YFinanceProvider (`data_providers/yfinance_provider.py`)

yfinance 是同步库，需要用 `asyncio.to_thread()` 包装为异步调用。

```python
class YFinanceProvider(DataProvider):
    """美股数据源。包装 yfinance，提供异步接口。"""

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """使用 yfinance.download() 获取 OHLCV 数据。
        - 确保返回的 DataFrame columns 统一为:
          ['Open', 'High', 'Low', 'Close', 'Volume']
        - 去掉 yfinance 可能返回的多级 columns。
        - 如果数据为空则 raise ValueError。
        """

    async def get_current_price(self, ticker: str) -> float:
        """使用 yfinance.Ticker(ticker).info 或 fast_info 获取最新价格。
        优先使用 fast_info['lastPrice'] 或 'regularMarketPrice'。
        """

    async def get_financials(self, ticker: str, period: str = "annual") -> dict:
        """返回 yfinance 的财务数据:
        {
            "income_statement": pd.DataFrame,
            "balance_sheet": pd.DataFrame,
            "cash_flow": pd.DataFrame,
        }
        period='annual' → .financials / .balance_sheet / .cashflow
        period='quarterly' → .quarterly_financials / ...
        """

    async def get_key_stats(self, ticker: str) -> dict:
        """返回:
        {
            "market_cap": float,
            "pe_ratio": float | None,
            "forward_pe": float | None,
            "beta": float | None,
            "dividend_yield": float | None,
            "sector": str | None,
            "industry": str | None,
            "52w_high": float,
            "52w_low": float,
        }
        从 yfinance.Ticker(ticker).info 提取。
        """

    def is_point_in_time(self) -> bool:
        return False  # yfinance 财报数据非 PIT

    def supported_asset_types(self) -> list[str]:
        return ["stock"]
```

### 4. CcxtProvider (`data_providers/ccxt_provider.py`)

```python
class CcxtProvider(DataProvider):
    """加密货币数据源。使用 ccxt 异步 API (默认 Binance)。"""

    def __init__(self, exchange_id: str = "binance"):
        """初始化 ccxt 异步交易所实例。"""

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """使用 exchange.fetch_ohlcv() 获取 K 线。
        - ticker 映射: "BTC" → "BTC/USDT", "ETH" → "ETH/USDT"
        - period 转换为起止时间戳
        - interval 映射: "1d" → "1d", "1h" → "1h", etc.
        - 返回统一格式 DataFrame (同 YFinanceProvider)
        """

    async def get_current_price(self, ticker: str) -> float:
        """使用 exchange.fetch_ticker() 获取最新价格。"""

    async def get_funding_rate(self, ticker: str) -> float | None:
        """获取永续合约 funding rate。
        仅对支持合约的交易所可用。
        如果不支持返回 None。
        """

    def is_point_in_time(self) -> bool:
        return True  # 交易所数据是实时的

    def supported_asset_types(self) -> list[str]:
        return ["btc", "eth"]

    async def close(self) -> None:
        """关闭 ccxt 异步连接。"""
```

### 5. FredProvider (`data_providers/fred_provider.py`)

```python
class FredProvider(DataProvider):
    """宏观经济数据源。使用 fredapi 获取 FRED 数据。"""

    def __init__(self, api_key: str | None = None):
        """api_key 可从环境变量 FRED_API_KEY 读取。
        如果未提供 key，记录警告但不报错（允许 mock 测试）。
        """

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """对于宏观指标, ticker 即 FRED series ID (如 'DGS10', 'FEDFUNDS')。
        返回单列 DataFrame, column='Close', index=DatetimeIndex。
        """

    async def get_current_price(self, ticker: str) -> float:
        """返回 FRED series 的最新值。"""

    # === 便捷方法 (Helper Methods) ===

    async def get_series(
        self, series_id: str, start: str | None = None, end: str | None = None
    ) -> pd.Series:
        """通用 FRED series 查询。"""

    async def get_fed_funds_rate(self) -> pd.Series:
        """FEDFUNDS series."""

    async def get_treasury_yield(self, maturity: str = "10y") -> pd.Series:
        """国债收益率。maturity: '2y','5y','10y','30y'
        映射: '10y' → 'DGS10', '2y' → 'DGS2', etc.
        """

    async def get_m2_money_supply(self) -> pd.Series:
        """M2 货币供应量 (M2SL series)。"""

    async def get_cpi(self) -> pd.Series:
        """CPI 数据 (CPIAUCSL series)。"""

    def is_point_in_time(self) -> bool:
        return True  # FRED 数据是 PIT 的

    def supported_asset_types(self) -> list[str]:
        return ["macro"]
```

### 6. Provider 工厂 (`data_providers/factory.py`)

```python
def get_provider(asset_type: str) -> DataProvider:
    """根据资产类型返回对应的 DataProvider 实例。

    asset_type:
        'stock' → YFinanceProvider
        'btc', 'eth' → CcxtProvider
        'macro' → FredProvider

    Raises ValueError for unknown asset_type.
    """
```

### 7. 目录结构

确保创建以下结构（含 `__init__.py`）：
```
data_providers/
├── __init__.py
├── base.py
├── yfinance_provider.py
├── ccxt_provider.py
├── fred_provider.py
└── factory.py
```

### 8. 测试 (`tests/test_004_data_providers.py`)

```python
# 1. test_factory_returns_correct_types
#    验证 get_provider("stock") 返回 YFinanceProvider
#    验证 get_provider("btc") 返回 CcxtProvider
#    验证 get_provider("macro") 返回 FredProvider
#    验证 get_provider("unknown") 抛出 ValueError

# 2. test_is_point_in_time
#    验证 YFinanceProvider.is_point_in_time() == False
#    验证 CcxtProvider.is_point_in_time() == True
#    验证 FredProvider.is_point_in_time() == True

# 3. test_supported_asset_types
#    验证各 provider 返回正确的 asset_type 列表

# 4. test_yfinance_get_price_history (需要网络，标记 @pytest.mark.network)
#    调用 YFinanceProvider().get_price_history("AAPL", period="5d")
#    验证返回 DataFrame 非空
#    验证 columns 包含 ['Open', 'High', 'Low', 'Close', 'Volume']

# 5. test_yfinance_get_current_price (需要网络，标记 @pytest.mark.network)
#    调用 YFinanceProvider().get_current_price("AAPL")
#    验证返回 float > 0

# 6. test_yfinance_get_key_stats (需要网络，标记 @pytest.mark.network)
#    调用 YFinanceProvider().get_key_stats("AAPL")
#    验证返回 dict 包含 "market_cap", "sector" 等 key

# 7. test_ccxt_provider_interface
#    实例化 CcxtProvider 并验证接口存在
#    如果能连接 Binance 公开 API，测试 get_current_price("BTC")
#    标记 @pytest.mark.network

# 8. test_fred_provider_no_key_graceful
#    不提供 API key 时，FredProvider 应该能实例化而不报错
#    调用 get_series 等方法应该抛出有意义的错误（而不是 crash）
```

**关于网络测试**: 标记为 `@pytest.mark.network` 的测试默认跑（yfinance 免费，无 key）。如果 CI/CD 环境无网络，可通过 `-m "not network"` 跳过。

## ✅ 验收标准 (Acceptance Criteria)
- `pyproject.toml` 存在且格式正确。
- `pip install -e ".[dev]"` 能成功安装（或至少 `pip install -e .` 不报错）。
- `pytest tests/test_004_data_providers.py -v` 通过（网络测试在有网络时通过）。
- `pytest tests/ -v` 全部通过（不破坏 test_001, test_002, test_003）。
- 代码遵循 PEP 8，使用 type hints。
- 所有新建目录有 `__init__.py`。

## ⚠️ 范围边界 (Out of Scope)
- Glassnode 集成 → Phase 3
- FMP Provider → Phase 3
- 新闻/情绪数据获取 → Task 007
- VIX 数据 → 可通过 yfinance 获取 `^VIX`，归入 YFinanceProvider 即可，不需要特殊处理
- pandas_ta 指标计算 → Task 005 (Technical Agent) 使用

---
**给 Developer Agent 的指令:**
请读取以上要求，一次性输出并创建所需的 Python 文件和目录结构。先创建 `pyproject.toml`，然后创建 `data_providers/` 目录下所有文件。写完后请先运行 `pip install -e ".[dev]"` 安装依赖，再运行 `pytest tests/test_004_data_providers.py -v`。如果报错，请自行修复直至测试通过。然后运行 `pytest tests/ -v` 确保不破坏已有测试。完成后必须在 `docs/AGENT_SYNC.md` 追加汇报，然后执行 `git add .` 和 `git commit`。
