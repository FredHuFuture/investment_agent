# Task 008: Signal Aggregator + E2E Pipeline (规则版)

## 🎯 任务目标 (Goal)
实现 **SignalAggregator**——将 TechnicalAgent、FundamentalAgent、MacroAgent 的输出进行加权合并，产出单一最终信号和综合分析报告。同时实现端到端 Pipeline，支持单一 ticker 的完整分析流程。

**本 Task 不使用 LLM。** 信号合并基于加权平均，完全确定性。LLM 推理在后续 Phase 2 作为可选增强引入。

## 📥 输入上下文 (Context)
- 架构设计参考 `docs/architecture_v4.md` 第 9.1 节 Signal Aggregator 和第 13 节 Build Plan。
- **依赖 Tasks 005-007 创建的 Agent 实现**：`agents/technical.py`, `agents/fundamental.py`, `agents/macro.py`。
- **依赖 Task 003 创建的 Portfolio 管理**：`portfolio/models.py`, `portfolio/manager.py`。
- **依赖 Task 004 创建的数据层**：`data_providers/` (YFinance, ccxt, FRED, factory)。
- 数据模型使用 `agents/models.py` 的 Signal, Regime, AgentInput, AgentOutput。

## 🛠️ 具体需求 (Requirements)

### 1. SignalAggregator (`engine/aggregator.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from agents.models import AgentOutput, Signal, Regime


@dataclass
class AggregatedSignal:
    """最终合并信号。"""
    ticker: str
    asset_type: str
    final_signal: Signal
    final_confidence: float          # 0-100
    regime: Regime | None            # 从 MacroAgent 获取
    agent_signals: list[AgentOutput] # 各 agent 原始输出
    reasoning: str                   # 综合推理
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "asset_type": self.asset_type,
            "final_signal": self.final_signal.value,
            "final_confidence": self.final_confidence,
            "regime": self.regime.value if self.regime else None,
            "agent_signals": [a.to_dict() for a in self.agent_signals],
            "reasoning": self.reasoning,
            "metrics": self.metrics,
            "warnings": self.warnings,
        }


class SignalAggregator:
    """加权合并多 Agent 信号。

    Phase 1: 静态默认权重。
    Phase 2: 从 agent_performance 表读取 learned weights。
    """

    # 默认权重 — 按 asset_type 区分
    DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
        "stock": {
            "TechnicalAgent": 0.35,
            "FundamentalAgent": 0.35,
            "MacroAgent": 0.30,
        },
        "btc": {
            "TechnicalAgent": 0.45,
            "MacroAgent": 0.55,
        },
        "eth": {
            "TechnicalAgent": 0.45,
            "MacroAgent": 0.55,
        },
    }

    def __init__(
        self,
        weights: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self._weights = weights or self.DEFAULT_WEIGHTS

    def aggregate(
        self,
        agent_outputs: list[AgentOutput],
        ticker: str,
        asset_type: str,
    ) -> AggregatedSignal:
        """合并所有 agent 信号。"""
        ...
```

### 2. 信号合并算法

#### 2.1 数值化 Signal

```python
SIGNAL_VALUE = {
    Signal.BUY: +1.0,
    Signal.HOLD: 0.0,
    Signal.SELL: -1.0,
}
```

#### 2.2 加权计算

```python
weights = self._weights.get(asset_type, self._weights["stock"])
total_weight = 0.0
weighted_sum = 0.0

for output in agent_outputs:
    agent_weight = weights.get(output.agent_name, 0.0)
    if agent_weight == 0.0:
        continue
    signal_value = SIGNAL_VALUE[output.signal]
    # 用 confidence 调整: 高置信信号权重更大
    confidence_factor = output.confidence / 100.0
    weighted_sum += signal_value * agent_weight * confidence_factor
    total_weight += agent_weight * confidence_factor

if total_weight > 0:
    raw_score = weighted_sum / total_weight  # 范围 [-1.0, +1.0]
else:
    raw_score = 0.0
```

#### 2.3 信号判定

| raw_score | Final Signal |
|-----------|-------------|
| >= +0.3   | BUY         |
| <= -0.3   | SELL        |
| 其他       | HOLD        |

**Confidence 计算:**
```python
# raw_score 距阈值越远, 信心越高
if final_signal == Signal.HOLD:
    confidence = 40 + (0.3 - abs(raw_score)) * (30 / 0.3)  # HOLD 时分数越接近0越确信
else:
    confidence = 50 + (abs(raw_score) - 0.3) * (40 / 0.7)
confidence = max(30.0, min(90.0, confidence))
```

### 3. Regime 提取

从 agent_outputs 中找到 MacroAgent 的输出，提取 `metrics["regime"]`:
```python
regime = None
for output in agent_outputs:
    if output.agent_name == "MacroAgent":
        regime_str = output.metrics.get("regime")
        if regime_str:
            regime = Regime(regime_str)
        break
```

### 4. 一致性检查 (Consensus Analysis)

在 metrics 中记录 agent 间的一致性：

```python
signals = [o.signal for o in agent_outputs]
buy_count = signals.count(Signal.BUY)
sell_count = signals.count(Signal.SELL)
hold_count = signals.count(Signal.HOLD)

# 一致性分数: 1.0 = 所有 agent 同向, 0.0 = 完全分裂
total = len(signals)
max_count = max(buy_count, sell_count, hold_count)
consensus_score = max_count / total if total > 0 else 0.0

# 如果有分歧, 降低 confidence
if consensus_score < 0.5:
    confidence *= 0.8  # 打 8 折
    warnings.append("Low agent consensus — signals conflict.")
```

### 5. Reasoning 字符串

```
"Final: BUY (score +0.52, confidence 68).
 Agents: Technical=BUY(72), Fundamental=BUY(65), Macro=BUY(58).
 Consensus: 3/3 agents agree (strong consensus).
 Regime: RISK_ON (net score +32).
 Weights: Technical 0.35, Fundamental 0.35, Macro 0.30."
```

如果有分歧:
```
"Final: HOLD (score +0.12, confidence 48).
 Agents: Technical=BUY(68), Fundamental=SELL(55), Macro=HOLD(42).
 Consensus: 1/3 agents — LOW CONSENSUS, reduced confidence.
 Regime: NEUTRAL.
 Note: Fundamental and Technical disagree — value concerns vs positive momentum."
```

### 6. Metrics 字典

```python
{
    "raw_score": float,          # [-1.0, +1.0]
    "consensus_score": float,    # [0.0, 1.0]
    "buy_count": int,
    "sell_count": int,
    "hold_count": int,
    "regime": str | None,
    "weights_used": dict[str, float],
    "agent_contributions": {
        "TechnicalAgent": {"signal": "BUY", "confidence": 72, "weighted_contribution": 0.18},
        ...
    },
}
```

### 7. AnalysisPipeline (`engine/pipeline.py`)

端到端分析管线，编排 DataProvider → Agents → Aggregator。

```python
class AnalysisPipeline:
    """单一 ticker 的完整分析流程。"""

    def __init__(
        self,
        db_path: str = "investment_agent.db",
    ) -> None:
        ...

    async def analyze_ticker(
        self,
        ticker: str,
        asset_type: str,
        portfolio: Portfolio | None = None,
    ) -> AggregatedSignal:
        """运行完整分析流程。

        1. 初始化合适的 DataProvider(s)
        2. 根据 asset_type 选择适用的 Agents
        3. 并行运行所有 Agent (asyncio.gather)
        4. 用 SignalAggregator 合并信号
        5. 返回 AggregatedSignal
        """
        # 1. 创建 providers
        from data_providers.factory import get_provider
        primary_provider = get_provider(asset_type)

        # 2. 初始化 agents
        agents = []
        agents.append(TechnicalAgent(primary_provider))

        if asset_type == "stock":
            agents.append(FundamentalAgent(primary_provider))

        # MacroAgent 需要两个 provider
        try:
            from data_providers.fred_provider import FredProvider
            from data_providers.yfinance_provider import YFinanceProvider
            fred_provider = FredProvider()
            vix_provider = YFinanceProvider()
            agents.append(MacroAgent(fred_provider, vix_provider))
        except Exception as exc:
            # FRED key 不可用时跳过 MacroAgent
            warnings.append(f"MacroAgent skipped: {exc}")

        # 3. 构造 AgentInput
        agent_input = AgentInput(
            ticker=ticker,
            asset_type=asset_type,
            portfolio=portfolio,
        )

        # 4. 并行运行
        results = await asyncio.gather(
            *[agent.analyze(agent_input) for agent in agents],
            return_exceptions=True,
        )

        # 5. 过滤异常, 收集有效输出
        agent_outputs = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                warnings.append(f"{agents[i].name} failed: {result}")
            else:
                agent_outputs.append(result)

        # 6. 合并
        aggregator = SignalAggregator()
        return aggregator.aggregate(agent_outputs, ticker, asset_type)
```

### 8. 错误处理

- **所有 Agent 都失败**: 返回 HOLD, confidence=30, warnings 列出失败原因。
- **部分 Agent 失败**: 用存活 Agent 的信号合并。自动调整权重（归一化到 1.0）。加 warning 注明哪些 Agent 缺失。
- **MacroAgent 无 FRED key**: 跳过 MacroAgent, 只用 Technical + Fundamental (stock) 或只用 Technical (crypto)。
- **空 agent_outputs**: 返回 HOLD, confidence=30, warning="No agent produced a signal."

### 9. 目录结构更新

```
engine/
├── __init__.py          # 已有
├── drift_analyzer.py    # 已有
├── aggregator.py        # NEW: SignalAggregator + AggregatedSignal
└── pipeline.py          # NEW: AnalysisPipeline
```

更新 `pyproject.toml` 确认 `engine` 已在 packages 中（应该已有）。

### 10. 测试 (`tests/test_008_signal_aggregator.py`)

所有测试 mock Agent 输出（不运行真实 Agent），直接测试 SignalAggregator 逻辑。

**辅助函数:**
```python
def _make_output(
    agent_name: str,
    signal: Signal,
    confidence: float,
    metrics: dict | None = None,
) -> AgentOutput:
    """快速构造 AgentOutput for testing。"""
```

**测试用例 (10 cases):**

1. **test_all_buy_produces_buy**: 3 个 Agent 都是 BUY → final=BUY, high confidence。

2. **test_all_sell_produces_sell**: 3 个 Agent 都是 SELL → final=SELL。

3. **test_mixed_produces_hold**: BUY + SELL + HOLD → final=HOLD (raw_score close to 0), low consensus warning。

4. **test_two_buy_one_hold**: 2 个 BUY, 1 个 HOLD → final=BUY (weighted sum should exceed +0.3)。

5. **test_confidence_weighting**: 同方向但不同 confidence。高 confidence agent 的贡献应更大。验证 raw_score 正确反映 confidence 差异。

6. **test_crypto_weights**: asset_type="btc", 只有 TechnicalAgent + MacroAgent。验证 FundamentalAgent 被忽略（权重为 0），且 crypto weights 被使用。

7. **test_consensus_score_calculation**: 验证 consensus_score 的正确性：3/3 agree → 1.0, 2/3 → 0.67, 各不同 → 0.33。

8. **test_low_consensus_reduces_confidence**: agents 完全分裂 → confidence 被乘以 0.8。

9. **test_empty_outputs_fallback**: 空列表 → HOLD, confidence=30, warning="No agent produced a signal."

10. **test_regime_extraction**: MacroAgent 输出含 `metrics["regime"] = "RISK_ON"` → AggregatedSignal.regime == Regime.RISK_ON。

11. **test_partial_agent_failure**: 给一个 Exception + 2 个正常输出 → 用 2 个正常输出合并, warnings 包含失败信息。

12. **test_aggregated_signal_to_dict**: 验证 `to_dict()` 输出格式完整，包含所有字段。

### 11. Pipeline 测试 (`tests/test_008_pipeline.py`)

Pipeline 测试 mock 所有 DataProvider，验证编排逻辑。

**测试用例 (3 cases):**

1. **test_pipeline_stock_e2e**: Mock providers → 运行 `analyze_ticker("AAPL", "stock")` → 返回 AggregatedSignal, 包含 3 个 agent_signals (Technical, Fundamental, Macro)。

2. **test_pipeline_crypto_no_fundamental**: Mock providers → `analyze_ticker("BTC", "btc")` → agent_signals 只包含 Technical + Macro（FundamentalAgent 不支持 crypto）。

3. **test_pipeline_no_fred_key**: Mock FredProvider 构造失败 → MacroAgent 被跳过 → 仍然返回结果, warnings 包含 "MacroAgent skipped"。

## ✅ 验收标准 (Acceptance Criteria)
- `pytest tests/test_008_signal_aggregator.py tests/test_008_pipeline.py -v` 全部通过。
- `pytest tests/ -v` 全部通过（不破坏已有测试）。
- 代码遵循 PEP 8，type hints，`from __future__ import annotations`。
- `engine/aggregator.py` 和 `engine/pipeline.py` 已创建。
- AggregatedSignal.to_dict() 可被 JSON 序列化。

## ⚠️ 范围边界 (Out of Scope)
- LLM 推理增强 → Phase 2 (Task 012)
- L1 Weight Adaptation (从 agent_performance 表学习权重) → Phase 2
- Position Sizing → Task 009 或 Phase 2
- Exit Trigger Engine → Phase 2
- Validation Agent (Forum 辩论) → Phase 2
- CLI 报告输出 → Task 009

---
**给 Developer Agent 的指令:**
请确认 `agents/technical.py`, `agents/fundamental.py`, `agents/macro.py` 已存在且测试通过（Tasks 005-007）。然后实现 `engine/aggregator.py` 和 `engine/pipeline.py` 及测试。Pipeline 测试需要 mock 所有 DataProvider 和 Agent，不做真实网络调用。写完后运行 `pytest tests/test_008_signal_aggregator.py tests/test_008_pipeline.py -v`，再运行 `pytest tests/ -v`。完成后在 `docs/AGENT_SYNC.md` 追加汇报，然后 `git add . && git commit`。
