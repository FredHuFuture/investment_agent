# Task 006: Fundamental Analysis Agent (规则版, 仅美股)

## 🎯 任务目标 (Goal)
实现 **FundamentalAgent**——基于财务比率的纯规则基本面分析引擎。通过 Value / Quality / Growth 三维打分生成投资信号。仅支持美股，不使用 LLM。

## 📥 输入上下文 (Context)
- 架构设计参考 `docs/architecture_v4.md` 第 8 节 Agent A: Fundamental Valuation。
- **依赖 Task 005 创建的共享框架**：`agents/models.py` (Signal, Regime, AgentInput, AgentOutput) 和 `agents/base.py` (BaseAgent ABC)。如果这些文件不存在，请先阅读 `tasks/005_technical_agent.md` 的 Section 1-2 创建它们。
- 数据来源：`data_providers/yfinance_provider.py` 的 `get_financials()` 和 `get_key_stats()`。
- yfinance 返回的财报数据非 Point-in-Time (non-PIT)，需在输出中标注 disclaimer。

## 🛠️ 具体需求 (Requirements)

### 1. FundamentalAgent (`agents/fundamental.py`)

```python
class FundamentalAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "FundamentalAgent"

    def supported_asset_types(self) -> list[str]:
        return ["stock"]  # 仅美股

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        self._validate_asset_type(agent_input)  # btc/eth → NotImplementedError

        # 1. 获取数据
        key_stats = await self._provider.get_key_stats(agent_input.ticker)
        financials = await self._provider.get_financials(agent_input.ticker)

        # 2. 提取指标
        metrics = self._extract_metrics(key_stats, financials)

        # 3. 计算三维评分
        value_score = self._compute_value_score(metrics)
        quality_score = self._compute_quality_score(metrics)
        growth_score = self._compute_growth_score(metrics)

        # 4. 综合 → 信号
        composite = value_score * 0.35 + quality_score * 0.35 + growth_score * 0.30
        signal, confidence = self._composite_to_signal(composite)

        # 5. 构造输出 (含 non-PIT warning)
        ...
```

### 2. 指标提取

从 `get_key_stats()` 直接获取:
- `pe_ratio` (trailing P/E)
- `forward_pe`
- `market_cap`
- `beta`
- `dividend_yield`
- `sector`, `industry`
- `52w_high`, `52w_low`

从 `get_financials()` 的 DataFrame 中计算:
- **P/B**: `market_cap / Total Stockholders Equity`
- **EV/EBITDA**: `(market_cap + Total Debt - Cash) / EBITDA`
- **ROE**: `Net Income / Total Stockholders Equity`
- **Profit Margin**: `Net Income / Total Revenue`
- **Revenue Growth**: `(latest Total Revenue - prior Total Revenue) / prior Total Revenue`
- **Debt/Equity**: `Total Debt / Total Stockholders Equity`
- **Current Ratio**: `Current Assets / Current Liabilities`
- **FCF Yield**: `Free Cash Flow / market_cap`
- **Pct from 52w High**: `(current_price - 52w_high) / 52w_high`

> **关键：防御性提取。** yfinance DataFrame 的行标签可能因公司不同而变化（例如 "Total Revenue" vs "Revenue"、"Stockholders Equity" vs "Total Stockholders' Equity"）。请实现一个 `_safe_extract(df, row_names: list[str]) -> float | None` 辅助函数，尝试多种行名变体，全部不命中则返回 None。

### 3. 三维评分系统

每个子分数范围 [-100, +100]。如果某个指标为 None（数据缺失），该项贡献 0 分。

#### Value Score (价值分, 权重 0.35)

| 指标 | 看多 (加分) | 看空 (扣分) | 中性 |
|------|-----------|-----------|------|
| P/E trailing | < 15: +25 | > 30: -20 | 15-30: 线性插值 +15 到 -10 |
| Forward P/E | < 12: +15 | > 25: -15 | 12-25: 插值 |
| P/B | < 2: +15 | > 5: -15 | 2-5: 插值 |
| EV/EBITDA | < 10: +20 | > 20: -15 | 10-20: 插值 |
| FCF Yield | > 8%: +15 | < 2%: -10 | 2-8%: 插值 |
| Pct from 52w High | < -30%: +10 | > -5%: -5 | 其他: 插值 |

Clamp to [-100, +100].

#### Quality Score (质量分, 权重 0.35)

| 指标 | 看多 | 看空 | 中性 |
|------|------|------|------|
| ROE | > 20%: +25 | < 5%: -20 | 5-20%: 插值 |
| Profit Margin | > 20%: +20 | < 5%: -15 | 5-20%: 插值 |
| Debt/Equity | < 0.5: +20 | > 2.0: -20 | 0.5-2.0: 插值 |
| Current Ratio | > 2.0: +15 | < 1.0: -20 | 1.0-2.0: 插值 |

Clamp to [-100, +100].

#### Growth Score (成长分, 权重 0.30)

| 指标 | 看多 | 看空 | 中性 |
|------|------|------|------|
| Revenue Growth | > 20%: +30 | < 0%: -25 | 0-20%: 插值 |
| Revenue Growth | > 50%: +40 (超高成长加分) | < -10%: -35 | — |
| Forward P/E < Trailing P/E | +15 (盈利预期增长) | Forward > Trailing×1.2: -10 | 其他: +5 |

Clamp to [-100, +100].

### 4. 综合计算与信号映射

```python
composite = value_score * 0.35 + quality_score * 0.35 + growth_score * 0.30
```

| 综合分 | 信号 |
|-------|------|
| >= +20 | BUY |
| <= -20 | SELL |
| 其他 | HOLD |

**Confidence**: 与 Technical Agent 类似的映射公式，但上限设为 **90**（因为 yfinance 数据非 PIT，需要额外审慎），下限 30。

### 5. Non-PIT Disclaimer

每次输出都必须在 `warnings` 中包含:
```python
"Data sourced from yfinance (non-point-in-time). "
"Fundamental metrics may reflect restated financials. "
"Do not use for backtesting without PIT adjustment."
```

### 6. Reasoning 字符串

```
"Value: moderately attractive (P/E 14.2, P/B 1.8, FCF yield 5.2%).
 Quality: strong (ROE 22%, margin 18%, low leverage D/E 0.4).
 Growth: moderate (revenue +12% YoY, forward P/E < trailing → earnings growth expected).
 ⚠ Non-PIT data — fundamental metrics may reflect restated financials."
```

### 7. Metrics 字典

```python
{
    "value_score": float,
    "quality_score": float,
    "growth_score": float,
    "composite_score": float,
    "pe_trailing": float | None,
    "pe_forward": float | None,
    "pb_ratio": float | None,
    "ev_ebitda": float | None,
    "roe": float | None,
    "profit_margin": float | None,
    "revenue_growth": float | None,
    "debt_equity": float | None,
    "current_ratio": float | None,
    "fcf_yield": float | None,
    "pct_from_52w_high": float | None,
    "market_cap": float | None,
    "dividend_yield": float | None,
    "sector": str | None,
}
```

### 8. 错误处理

- `get_financials()` 或 `get_key_stats()` 抛出异常（如 ETF、SPAC 无财报）→ 返回 HOLD, confidence=30, 带 warning 解释数据不可用。
- 每个指标提取 try/except → 默认 None。即使所有指标为 None 也能正常输出（HOLD, confidence 30）。
- Crypto asset_type → `NotImplementedError` (通过 `_validate_asset_type()`)

### 9. 测试 (`tests/test_006_fundamental_agent.py`)

所有测试 mock DataProvider 的 `get_financials()` 和 `get_key_stats()`。

**辅助函数:**
```python
def _mock_key_stats(overrides: dict | None = None) -> dict:
    """返回合理默认值的 key_stats dict。"""
    base = {
        "market_cap": 500_000_000_000, "pe_ratio": 18.0, "forward_pe": 15.0,
        "beta": 1.1, "dividend_yield": 0.01, "sector": "Technology",
        "industry": "Software", "52w_high": 200.0, "52w_low": 140.0,
    }
    if overrides: base.update(overrides)
    return base

def _mock_financials() -> dict:
    """返回含 income_statement, balance_sheet, cash_flow DataFrame 的 dict。
    包含行: Total Revenue, Net Income, Total Stockholders Equity, Total Debt,
    Current Assets, Current Liabilities, Free Cash Flow, EBITDA 等。
    """
```

**测试用例:**

1. **test_high_quality_value_stock**: P/E=12, ROE=25%, revenue growth=15%, 低负债 → BUY, confidence >= 65。

2. **test_overvalued_stock**: P/E=45, P/B=8, FCF yield=1% → SELL。

3. **test_mediocre_stock**: P/E=22, ROE=10%, revenue flat → HOLD。

4. **test_crypto_raises_not_implemented**: asset_type="btc" → NotImplementedError。

5. **test_missing_financials_graceful**: mock get_financials 抛 ValueError → HOLD, low confidence, 有 warning。

6. **test_non_pit_warning_present**: 断言每次调用输出 warnings 包含 non-PIT disclaimer。

7. **test_all_none_metrics**: 空 financials + 空 key_stats → HOLD, confidence ~30, 不 crash。

8. **test_metrics_keys_present**: 断言 metrics dict 包含所有期望 key。

## ✅ 验收标准 (Acceptance Criteria)
- `pytest tests/test_006_fundamental_agent.py -v` 全部通过。
- `pytest tests/ -v` 全部通过（不破坏已有测试）。
- 代码遵循 PEP 8，type hints，`from __future__ import annotations`。
- `agents/fundamental.py` 已创建。

## ⚠️ 范围边界 (Out of Scope)
- DCF 估值模型 → Phase 2 (LLM + detailed modeling)
- Sector 横向对比 → Phase 2
- LLM 推理 → Task 008
- BTC/Crypto 基本面 → 不适用

---
**给 Developer Agent 的指令:**
请确认 `agents/models.py` 和 `agents/base.py` 已存在（由 Task 005 创建）。如果不存在，请先按 `tasks/005_technical_agent.md` 的 Section 1-2 创建它们。然后实现 `agents/fundamental.py` 和测试。写完后运行 `pytest tests/test_006_fundamental_agent.py -v`，再运行 `pytest tests/ -v`。完成后在 `docs/AGENT_SYNC.md` 追加汇报，然后 `git add . && git commit`。
