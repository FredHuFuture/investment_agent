# Task 005: Agent 框架 + Technical Analysis Agent (规则版)

## 🎯 任务目标 (Goal)
1. 建立 **Agent 框架**——共享的枚举、输入/输出数据模型和抽象基类。
2. 实现 **TechnicalAgent**——基于 pandas_ta 的纯规则技术分析引擎（本 Task 不使用 LLM）。

## 📥 输入上下文 (Context)
- 架构设计参考 `docs/architecture_v4.md` 第 8 节 `Analysis Agents`。
- DataProvider 已在 Task 004 中完成：`data_providers/base.py` (ABC), `yfinance_provider.py`, `ccxt_provider.py`。
- 本 Task 的 TechnicalAgent 通过 DataProvider 获取 OHLCV 数据，用 pandas_ta 计算指标，用规则生成信号。
- pandas_ta 已在 `pyproject.toml` 中声明为依赖。
- 后续 Task 006, 007 将依赖本 Task 创建的 `agents/models.py` 和 `agents/base.py`。

## 🛠️ 具体需求 (Requirements)

### 1. 共享类型 (`agents/models.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from portfolio.models import Portfolio  # 已有类型


class Signal(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class Regime(str, Enum):
    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"


@dataclass
class AgentInput:
    ticker: str
    asset_type: str  # "stock" | "btc" | "eth"
    portfolio: Portfolio | None = None
    regime: Regime | None = None
    learned_weights: dict[str, Any] = field(default_factory=dict)
    approved_rules: list[str] = field(default_factory=list)


@dataclass
class AgentOutput:
    agent_name: str
    ticker: str
    signal: Signal
    confidence: float  # 0.0 ~ 100.0
    reasoning: str
    metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not 0.0 <= self.confidence <= 100.0:
            raise ValueError(f"confidence must be 0-100, got {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "ticker": self.ticker,
            "signal": self.signal.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "warnings": self.warnings,
        }
```

### 2. 抽象基类 (`agents/base.py`)

```python
from abc import ABC, abstractmethod
from data_providers.base import DataProvider

class BaseAgent(ABC):
    """所有 Analysis Agent 的抽象基类。"""

    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent 名称，如 'TechnicalAgent'。"""

    @abstractmethod
    def supported_asset_types(self) -> list[str]: ...

    @abstractmethod
    async def analyze(self, agent_input: AgentInput) -> AgentOutput: ...

    def _validate_asset_type(self, agent_input: AgentInput) -> None:
        if agent_input.asset_type not in self.supported_asset_types():
            raise NotImplementedError(
                f"{self.name} does not support '{agent_input.asset_type}'. "
                f"Supported: {self.supported_asset_types()}"
            )

    def _clamp_confidence(self, value: float) -> float:
        return max(0.0, min(100.0, value))
```

### 3. TechnicalAgent (`agents/technical.py`)

#### 3.1 数据获取

```python
class TechnicalAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "TechnicalAgent"

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        # 1. Fetch daily OHLCV (period="1y", interval="1d")
        daily_df = await self._provider.get_price_history(
            agent_input.ticker, period="1y", interval="1d"
        )
        # 2. Fetch weekly OHLCV (period="2y", interval="1wk") — 用于趋势确认
        #    如果获取失败则跳过，加 warning
        # 3. 计算指标 → 评分 → 生成信号
```

#### 3.2 技术指标计算 (pandas_ta)

| 指标 | 参数 | 用途 |
|------|------|------|
| SMA 20 | `ta.sma(close, length=20)` | 短期趋势 |
| SMA 50 | `ta.sma(close, length=50)` | 中期趋势 |
| SMA 200 | `ta.sma(close, length=200)` | 长期趋势 |
| RSI 14 | `ta.rsi(close, length=14)` | 动量震荡 |
| MACD | `ta.macd(close, fast=12, slow=26, signal=9)` | 趋势动量 |
| Bollinger Bands | `ta.bbands(close, length=20, std=2.0)` | 波动率通道 |
| ATR 14 | `ta.atr(high, low, close, length=14)` | 波动率度量 |
| Volume SMA 20 | `ta.sma(volume, length=20)` | 成交量趋势 |

> **注意**: pandas_ta 的 MACD 返回 DataFrame，columns 名类似 `MACD_12_26_9`, `MACDh_12_26_9`, `MACDs_12_26_9`。请使用 `.iloc[:, 0/1/2]` 或通过列名模式匹配访问。

#### 3.3 评分系统 (三个子分数，各 [-100, +100])

**Trend Score (趋势分, 权重 0.45):**

| 条件 | 分数 |
|------|------|
| Price > SMA 20 | +10 |
| Price > SMA 50 | +10 |
| Price > SMA 200 | +15 |
| SMA 20 > SMA 50 (金叉排列) | +15 |
| SMA 50 > SMA 200 | +15 |
| Price < SMA 20 | -10 |
| Price < SMA 50 | -10 |
| Price < SMA 200 | -15 |
| SMA 20 < SMA 50 (死叉排列) | -15 |
| SMA 50 < SMA 200 | -15 |
| Weekly SMA 20 > Weekly SMA 50 (周线确认) | +10 |
| Weekly SMA 20 < Weekly SMA 50 (周线矛盾) | -10 |

如果数据不足以计算 SMA 200，跳过相关条件，加 warning。

**Momentum Score (动量分, 权重 0.35):**

| 条件 | 分数 |
|------|------|
| RSI > 50 且 < 70 (健康看多) | +20 |
| RSI >= 70 (超买) | -10 |
| RSI < 30 (超卖，可能反弹) | +10 |
| RSI >= 30 且 < 50 (看空动量) | -15 |
| MACD line > signal line | +20 |
| MACD line < signal line | -20 |
| MACD histogram 最近 3 根上升 | +15 |
| MACD histogram 最近 3 根下降 | -15 |
| Volume > Volume SMA 20 × 1.5 (且趋势一致) | +10 |
| Volume < Volume SMA 20 × 0.5 (低量) | -5 |

**Volatility Score (波动率分, 权重 0.20):**

| 条件 | 分数 |
|------|------|
| Price 接近下轨 (距 BB Lower < 5%) | +15 |
| Price 接近上轨 (距 BB Upper < 5%) | -10 |
| Price 在中间区域 | +5 |
| ATR 最近 5 根递减 (波动收缩) | +10 |
| ATR 最近 5 根递增 + 趋势看空 | -15 |
| ATR 最近 5 根递增 + 趋势看多 | +5 |
| BB 宽度收窄 (squeeze) | +5 |

#### 3.4 综合计算与信号映射

```python
composite = trend_score * 0.45 + momentum_score * 0.35 + volatility_score * 0.20
# composite 范围: [-100, +100]
```

| 综合分范围 | 信号 | 置信度公式 |
|-----------|------|-----------|
| >= +25 | BUY | `50 + (composite - 25) * (50 / 75)`, clamp [30, 95] |
| <= -25 | SELL | `50 + (abs(composite) - 25) * (50 / 75)`, clamp [30, 95] |
| -25 < x < +25 | HOLD | `50 - abs(composite) * (50 / 25)`, clamp [30, 95] |

#### 3.5 Reasoning 字符串

拼接各子分数的关键信号，例如：
```
"Trend: bullish (SMA alignment above 200, golden cross).
 Momentum: moderately bullish (RSI 58, MACD above signal).
 Volatility: neutral (mid-Bollinger, ATR stable).
 Weekly: confirms daily trend."
```

#### 3.6 Metrics 字典

```python
{
    "trend_score": float,
    "momentum_score": float,
    "volatility_score": float,
    "composite_score": float,
    "sma_20": float,
    "sma_50": float,
    "sma_200": float | None,
    "rsi_14": float,
    "macd_line": float,
    "macd_signal": float,
    "macd_histogram": float,
    "bb_upper": float,
    "bb_lower": float,
    "bb_middle": float,
    "atr_14": float,
    "current_price": float,
    "volume_ratio": float,
    "weekly_trend_confirms": bool | None,
}
```

#### 3.7 错误处理

- 日线数据 < 200 行：SMA 200 跳过，加 warning
- 周线数据获取失败：weekly confirmation 跳过，score 设 0，加 warning
- 任何指标返回 NaN：该项 score 设 0，加 warning
- 数据完全为空：raise ValueError

### 4. 目录结构

```
agents/
├── __init__.py        # 导出 BaseAgent, AgentInput, AgentOutput, Signal, Regime, TechnicalAgent
├── models.py          # Signal, Regime 枚举 + AgentInput, AgentOutput 数据类
├── base.py            # BaseAgent ABC
└── technical.py       # TechnicalAgent 实现
```

同时修复已有的 tech debt：
- 创建 `engine/__init__.py`（当前缺失）

更新 `pyproject.toml` 的 `[tool.hatch.build.targets.wheel]` packages 列表，添加 `"agents"`。

### 5. 测试 (`tests/test_005_technical_agent.py`)

所有测试 mock DataProvider，不做网络调用。

**辅助函数:**
```python
def _make_ohlcv(prices: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    """根据 close 价格列表构造 OHLCV DataFrame。
    Open/High/Low 作为 close 的微小变化生成。
    dates 为从今天往前的工作日。
    """
```

**测试用例:**

1. **test_bullish_trending_stock**: 250 根日线稳步上涨 (100→200)。断言 signal=BUY, confidence >= 60, trend_score > 0。

2. **test_bearish_trending_stock**: 250 根日线稳步下跌 (200→100)。断言 signal=SELL, confidence >= 55。

3. **test_sideways_produces_hold**: 250 根在 95-105 之间震荡。断言 signal=HOLD。

4. **test_overbought_rsi_dampens**: 上涨趋势但末尾急涨导致 RSI > 70。断言 momentum_score 被压制。

5. **test_crypto_asset_works**: asset_type="btc"，不报错，返回有效信号。

6. **test_insufficient_data_warns**: 只有 50 根日线。断言 warnings 非空（SMA 200 不可用），但不 crash。

7. **test_output_structure**: 验证 AgentOutput 所有字段存在，`to_dict()` 正常，confidence 在 [30, 95]，signal 是有效 Signal 枚举。

8. **test_metrics_keys_present**: 断言 metrics dict 包含所有期望 key。

## ✅ 验收标准 (Acceptance Criteria)
- `pytest tests/test_005_technical_agent.py -v` 全部通过。
- `pytest tests/ -v` 全部通过（不破坏 test_001 ~ test_004）。
- 代码遵循 PEP 8，使用 type hints，`from __future__ import annotations`。
- `agents/` 目录含 `__init__.py`, `models.py`, `base.py`, `technical.py`。
- `engine/__init__.py` 已创建。

## ⚠️ 范围边界 (Out of Scope)
- LLM 推理 → Task 008
- Fundamental / Macro / Sentiment agents → Tasks 006, 007
- Skill System (YAML 策略模块) → Phase 2
- L1 权重自适应 → Phase 2

---
**给 Developer Agent 的指令:**
请读取以上要求，一次性创建所有文件。先创建 `agents/models.py` 和 `agents/base.py`（后续 Task 006/007 也依赖它们），再实现 `agents/technical.py` 和测试。写完后运行 `pytest tests/test_005_technical_agent.py -v`，再运行 `pytest tests/ -v` 确保无回归。完成后必须在 `docs/AGENT_SYNC.md` 追加汇报，然后执行 `git add .` 和 `git commit`。
