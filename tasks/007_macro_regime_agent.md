# Task 007: Macro/Regime Detection Agent (规则版)

## 🎯 任务目标 (Goal)
实现 **MacroAgent**——基于 FRED 宏观数据和 VIX 的纯规则 regime 识别引擎。通过多指标积分系统判断当前宏观环境属于 RISK_ON / RISK_OFF / NEUTRAL，并据此为目标资产提供信号。

## 📥 输入上下文 (Context)
- 架构设计参考 `docs/architecture_v4.md` 第 8 节 Agent E: Macro Liquidity 和第 10.3 节 L2: Regime-Aware Strategy Switching。
- **依赖 Task 005 创建的共享框架**：`agents/models.py` (Signal, Regime, AgentInput, AgentOutput) 和 `agents/base.py` (BaseAgent ABC)。
- 数据来源：
  - `data_providers/fred_provider.py` → Fed Funds, 10Y/2Y 国债收益率, M2 货币供应量
  - `data_providers/yfinance_provider.py` → VIX (^VIX 的 OHLCV 数据)
- MacroAgent 需要 **两个 DataProvider**（FredProvider + YFinanceProvider）。

## 🛠️ 具体需求 (Requirements)

### 1. MacroAgent (`agents/macro.py`)

```python
class MacroAgent(BaseAgent):
    """宏观环境分析 + Regime 识别。

    与其他 Agent 不同，MacroAgent 需要两个 DataProvider:
    - FredProvider (primary, 传给 BaseAgent.__init__)
    - YFinanceProvider (secondary, 用于获取 VIX)
    """

    def __init__(
        self,
        fred_provider: DataProvider,
        vix_provider: DataProvider,
    ) -> None:
        super().__init__(provider=fred_provider)
        self._vix_provider = vix_provider

    @property
    def name(self) -> str:
        return "MacroAgent"

    def supported_asset_types(self) -> list[str]:
        return ["stock", "btc", "eth"]  # 宏观环境影响所有资产

    async def analyze(self, agent_input: AgentInput) -> AgentOutput:
        # 1. 获取宏观数据
        macro_data = await self._fetch_macro_data()
        # 2. Regime 分类
        regime, risk_on_pts, risk_off_pts, net_score = self._classify_regime(macro_data)
        # 3. 根据 regime × asset_type 生成信号
        signal = self._regime_to_signal(regime, agent_input.asset_type)
        confidence = self._compute_confidence(net_score)
        # 4. 构造输出
        ...
```

### 2. 宏观数据获取

| 指标 | 数据源 | 获取方法 |
|------|--------|---------|
| VIX (当前值) | YFinanceProvider | `get_price_history("^VIX", period="3mo", interval="1d")` → 取最新 Close |
| VIX 20日均值 | 计算 | `SMA(vix_close, 20)` 最新值 |
| Fed Funds Rate | FredProvider | `get_fed_funds_rate()` → 取最新值 |
| 10Y 国债收益率 | FredProvider | `get_treasury_yield("10y")` → 取最新值 |
| 2Y 国债收益率 | FredProvider | `get_treasury_yield("2y")` → 取最新值 |
| Yield Curve Spread | 计算 | `10Y - 2Y` |
| M2 YoY 增速 | FredProvider | `get_m2_money_supply()` → 计算 `(latest / 12个月前 - 1)` |
| Fed Funds 趋势 | 计算 | 比较当前值 vs 3个月前：下降/上升/不变 |

每个数据获取应 try/except，失败则设为 None 并加 warning。

### 3. Regime 分类 (积分制)

每个条件贡献 RISK_ON 分 或 RISK_OFF 分:

| 条件 | RISK_ON | RISK_OFF |
|------|---------|----------|
| VIX < 15 | +20 | 0 |
| VIX 15-20 | +10 | 0 |
| VIX 20-25 | 0 | +10 |
| VIX 25-30 | 0 | +20 |
| VIX > 30 | 0 | +30 |
| VIX < VIX SMA20 (波动率下降) | +10 | 0 |
| VIX > VIX SMA20 × 1.2 (波动率飙升) | 0 | +15 |
| Yield Curve > +0.5% (正常) | +15 | 0 |
| Yield Curve 0% ~ +0.5% (平坦) | +5 | +5 |
| Yield Curve < 0% (倒挂) | 0 | +25 |
| Fed Funds 下降趋势 (在降息) | +15 | 0 |
| Fed Funds 上升趋势 (在加息) | 0 | +10 |
| Fed Funds 不变 | +5 | +5 |
| M2 YoY > 5% (宽松) | +15 | 0 |
| M2 YoY 0% ~ 5% (温和) | +5 | +5 |
| M2 YoY < 0% (紧缩) | 0 | +20 |

如果某项数据为 None（获取失败），该项得分全部为 0（即不贡献任何方向）。

**Net Score & Regime 判定:**

```python
net_score = risk_on_points - risk_off_points
```

| Net Score | Regime |
|-----------|--------|
| >= +15 | RISK_ON |
| <= -15 | RISK_OFF |
| -15 < x < +15 | NEUTRAL |

### 4. 信号映射 (Regime × Asset Type)

| Regime | stock | btc / eth |
|--------|-------|-----------|
| RISK_ON | BUY | BUY |
| RISK_OFF | SELL | SELL |
| NEUTRAL | HOLD | HOLD |

### 5. Confidence 计算

```python
# 理论最大 net_score ≈ 80 (所有指标同向)
max_possible = 80.0
raw_confidence = 40 + abs(net_score) * (50 / max_possible)
confidence = clamp(raw_confidence, 35, 85)
```

上限 85：宏观信号固有滞后性，不应过度自信。

### 6. Reasoning 字符串

```
"Regime: RISK_ON (net score +32).
 VIX: 16.5 (below 20, declining vs SMA20).
 Yield curve: +0.82% (positive spread, no inversion).
 Fed Funds: 4.25% (holding steady, no recent changes).
 M2 YoY: +3.2% (moderate growth).
 Macro environment supports risk assets."
```

### 7. Metrics 字典

```python
{
    "regime": str,  # "RISK_ON" | "RISK_OFF" | "NEUTRAL"
    "net_score": float,
    "risk_on_points": float,
    "risk_off_points": float,
    "vix_current": float | None,
    "vix_sma_20": float | None,
    "fed_funds_rate": float | None,
    "treasury_10y": float | None,
    "treasury_2y": float | None,
    "yield_curve_spread": float | None,
    "m2_yoy_growth": float | None,
    "fed_funds_trend": str | None,  # "decreasing" | "increasing" | "stable"
}
```

### 8. 错误处理

- **FRED API key 缺失**: FredProvider 会抛出 `RuntimeError`。MacroAgent 捕获后返回 HOLD, confidence=30, warning="FRED API key not configured. Macro analysis unavailable."
- **VIX 数据不可用**: 捕获异常，跳过 VIX 相关项（得分全部设 0），加 warning。Regime 仍可通过 FRED 数据部分判定。
- **M2 历史不足**: M2 是月度数据，如果历史不到 12 个月无法算 YoY。跳过，加 warning。
- **所有数据都获取失败**: 返回 NEUTRAL regime, HOLD signal, confidence=30, warnings 列出所有失败项。

### 9. 测试 (`tests/test_007_macro_agent.py`)

所有测试 mock FredProvider 和 YFinanceProvider。

**辅助函数:**
```python
def _mock_vix_data(vix_value: float, num_days: int = 60) -> pd.DataFrame:
    """生成 VIX OHLCV DataFrame, Close 设为指定值。"""

async def _mock_fred_series(values: list[float], months_back: int = 12) -> pd.Series:
    """生成月度 FRED Series。"""
```

**Mock 策略:** 创建自定义的 `MockFredProvider` 和 `MockVixProvider` 类（继承 DataProvider 或直接 duck-typing），返回预设数据。或者使用 unittest.mock.AsyncMock 来 mock provider 方法。

**测试用例 (9 cases):**

1. **test_risk_on_regime**: VIX=14, yield curve=+1.0%, Fed Funds 下降, M2 growth=6% → regime=RISK_ON, signal=BUY。

2. **test_risk_off_regime**: VIX=32, yield curve=-0.5% (倒挂), Fed Funds 上升, M2 growth=-2% → regime=RISK_OFF, signal=SELL。

3. **test_neutral_regime**: VIX=22, yield curve=+0.2%, Fed Funds 不变, M2 growth=3% → regime=NEUTRAL, signal=HOLD。

4. **test_crypto_buy_in_risk_on**: 同 test 1 数据，asset_type="btc" → signal=BUY。

5. **test_crypto_sell_in_risk_off**: 同 test 2 数据，asset_type="btc" → signal=SELL。

6. **test_missing_fred_key_graceful**: Mock FredProvider 所有方法都抛 RuntimeError → HOLD, confidence=30, warning 包含 "FRED"。

7. **test_missing_vix_graceful**: Mock VIX 获取失败 → regime 仍可部分判定（仅用 FRED 数据），有 warning。

8. **test_regime_in_metrics**: 断言 `output.metrics["regime"]` 是有效的 Regime 值 ("RISK_ON" | "RISK_OFF" | "NEUTRAL")。

9. **test_yield_curve_inversion**: 10Y=3.5%, 2Y=4.0% → yield_curve_spread=-0.5%, 贡献 RISK_OFF +25 分。断言 metrics 中 yield_curve_spread 正确。

## ✅ 验收标准 (Acceptance Criteria)
- `pytest tests/test_007_macro_agent.py -v` 全部通过。
- `pytest tests/ -v` 全部通过（不破坏已有测试）。
- 代码遵循 PEP 8，type hints，`from __future__ import annotations`。
- `agents/macro.py` 已创建。

## ⚠️ 范围边界 (Out of Scope)
- LLM 宏观推理 → Task 008
- DXY (美元指数) → 可选的 Phase 2 增强
- BTC 链上数据 (MVRV, SOPR) → Phase 2 BTC On-chain Agent
- L2 Regime Switching 策略联动 → Phase 2
- 新闻/情绪分析 → Task 008 或 Phase 2

---
**给 Developer Agent 的指令:**
请确认 `agents/models.py` 和 `agents/base.py` 已存在（由 Task 005 创建）。然后实现 `agents/macro.py` 和测试。写完后运行 `pytest tests/test_007_macro_agent.py -v`，再运行 `pytest tests/ -v`。完成后在 `docs/AGENT_SYNC.md` 追加汇报，然后 `git add . && git commit`。
