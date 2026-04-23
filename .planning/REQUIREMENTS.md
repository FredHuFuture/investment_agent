# Requirements: Investment Agent — v1.1 Live Validation

**Defined:** 2026-04-22
**Milestone:** v1.1 Live Validation
**Core Value:** Drawdown protection via thesis-aware, regime-aware multi-agent signals — catching when a held position no longer matches the reason it was bought.
**Milestone Goal:** Transition from "ships clean code" to "actually used weekly for 5-10 US equity positions" — with signal noise surfaced, triaged, and actionable, not buried in preliminary-calibration flags.

> See `.planning/milestones/v1.0-REQUIREMENTS.md` for shipped v1.0 foundation. This milestone extends it with live data, calibration visibility, and weekly-cadence tooling.

## Operating assumptions (tighten scope)

- **Cadence:** weekly review + research (NOT daily, NOT alert-driven)
- **Universe:** 5-10 US equity tickers (AAPL, NVDA, MSFT, etc.) — crypto + wider universe deferred
- **Operator:** solo user, personal-investing tool; no multi-tenant
- **Top rough edge:** signal noise — north star for this milestone is "user trusts what the dashboard says"

## v1.1 Requirements

### Live Data & Calibration (LIVE)

- [ ] **LIVE-01**: Populate `backtest_signal_history` corpus across all 5-10 tickers in the user's portfolio (3+ years of cached OHLCV each); expose a `POST /api/v1/calibration/rebuild-corpus` endpoint that invokes `rebuild_signal_corpus` per ticker with progress reporting; background job mode for long runs — `daemon/jobs.py::rebuild_signal_corpus` + `api/routes/calibration.py`
- [ ] **LIVE-02**: `CalibrationPage.tsx` frontend surface at `/calibration` showing per-agent Brier score, rolling IC, IC-IR, and a 90-day sparkline trend per agent; each row clickable to drill into per-ticker agent history — `frontend/src/pages/CalibrationPage.tsx` (new) + extends `/analytics/calibration` endpoint
- [ ] **LIVE-03**: Agent weight management UI — `WeightsPage.tsx` (or embedded in CalibrationPage) showing current weights, IC-IR-suggested weights, a "Apply IC-IR weights" button that persists to `agent_weights` table + a per-agent manual override toggle (e.g., "exclude TechnicalAgent from Stock analysis until I re-enable") — `engine/weight_adapter.py` + new `frontend/src/pages/WeightsPage.tsx` + `agent_weights` table schema
- [ ] **LIVE-04**: Weekly digest — `POST /api/v1/digest/weekly` endpoint renders a Markdown digest covering (a) portfolio performance vs benchmark this week, (b) top 5 signal flips this week, (c) agents whose IC-IR moved >20%, (d) open thesis drift alerts, (e) action items. Opt-in email delivery via existing notification channel. Scheduled job runs every Sunday 18:00. — `engine/digest.py` (new) + `api/routes/digest.py` + `daemon/scheduler.py` + existing email/Telegram channels

### UAT Closeout from v1.0 (CLOSE)

- [ ] **CLOSE-01**: Close Phase 3 human-UAT — run `pip install -e ".[llm-local]"` + `python scripts/fetch_finbert.py`; confirm FinBERT returns non-HOLD on real news-rich ticker (NVDA earnings week). Document result in `03-HUMAN-UAT.md` + run `/gsd-verify-work 3` to flip status from `partial` to `resolved`.
- [ ] **CLOSE-02**: Close Phase 3 human-UAT — set `FINNHUB_API_KEY` to a real free-tier key; confirm `FinnhubProvider.get_sector_pe("technology")` returns a float; confirm `FundamentalAgent` reasoning on AAPL contains `"Finnhub sector P/E"` string. Document in `03-HUMAN-UAT.md`.
- [ ] **CLOSE-03**: Close Phase 3 human-UAT — launch daemon, confirm `data/daemon.pid` contains live PID matching process; confirm `netstat -an` shows `127.0.0.1:8000 LISTEN` (not `0.0.0.0`); kill daemon, verify PID file removed by atexit. Document in `03-HUMAN-UAT.md`.
- [ ] **CLOSE-04**: Close Phase 4 human-UAT — target-weight browser flow (set, persist on reload, clear, invalid-input alert). Document in `04-HUMAN-UAT.md`.
- [ ] **CLOSE-05**: Close Phase 4 human-UAT — MonitoringPage rules panel (toggle STOP_LOSS_HIT off, confirm daemon log excludes it on next run). Document in `04-HUMAN-UAT.md`.
- [ ] **CLOSE-06**: Close Phase 4 human-UAT — DailyPnlHeatmap tooltip on hover with date + P&L + correct color. Document in `04-HUMAN-UAT.md`.

### Analytics Completeness (AN)

- [ ] **AN-01**: Dividend-aware IRR — reuse YFinance dividend history (already available via `get_dividends` or `Ticker.dividends`) to add dividend cash-flows into IRR computation; update `engine/analytics.py::compute_irr_multi` to accept a `dividends: list[(date, amount)]` parameter; tests verify dividend-paying stocks (e.g., MSFT, KO) now report higher IRR than dividend-less computation. Backward-compat: parameter defaults to empty list.
- [ ] **AN-02**: Signal drift detector — new `engine/drift_detector.py` evaluates per-agent IC-IR weekly; when IC-IR drops >20% below 60-day average (or falls below 0.5 for 2 consecutive weekly runs), emits alert via existing notification channel AND auto-scales the agent's next weight via WeightAdapter. Visible in CalibrationPage as "drift detected" badge.

## v2 Requirements (deferred beyond v1.1)

Ideas surfaced in v1.0 retrospective or v1.1 scoping, deferred here so they aren't re-discovered.

### Deployment (was DEPLOY-v2-*, promoted to active candidates for v1.2)

- **DEPLOY-v2-01**: Docker + docker-compose.yml
- **DEPLOY-v2-02**: OpenTelemetry + Prometheus metrics
- **DEPLOY-v2-03**: `pandas-ta-classic` migration

### UX Depth (was UI-v2-*, candidates for v1.3)

- **UI-v2-01**: Allocation donut charts on PortfolioPage
- **UI-v2-02**: Broker CSV import wizard UI
- **UI-v2-03**: Alert-threshold editing in UI
- **UI-v2-04**: Riskfolio-Lib position-sizing (Kelly / risk parity / Black-Litterman)
- **UI-v2-05**: QuantStats HTML tearsheet endpoint

### Signal Quality v2 (candidates for v1.4)

- **SIG-v2-01**: Calibration reliability plot / diagram (partially addressed by LIVE-02 sparkline but full reliability diagram deferred)
- **SIG-v2-02**: Regime-conditioned adaptive RSI thresholds
- **SIG-v2-03**: Jesse-style trade-order-shuffle Monte Carlo

### Data Coverage v2

- **DATA-v2-01**: MarketAux news + pre-computed sentiment
- **DATA-v2-02**: SimFin point-in-time fundamentals
- **DATA-v2-03**: CoinGecko GeckoTerminal DEX on-chain

## Out of Scope for v1.1

| Feature | Reason |
|---------|--------|
| Crypto-heavy calibration | User confirmed mostly US equities; crypto IC-IR deferred to a later crypto-focused milestone |
| Wider ticker universe (20+) | User confirmed 5-10 tickers; scale-testing deferred |
| Daily cadence optimizations | Cadence is weekly; dashboard load time is not the bottleneck |
| Docker / deploy story | v1.2 milestone material |
| Allocation donuts / CSV import / Riskfolio | v1.3 milestone material |
| Mobile / SaaS / broker execution | Permanent out of scope per PROJECT.md |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| LIVE-01 | Phase 5 | Pending |
| CLOSE-01 | Phase 5 | Pending |
| CLOSE-02 | Phase 5 | Pending |
| CLOSE-03 | Phase 5 | Pending |
| LIVE-02 | Phase 6 | Pending |
| LIVE-03 | Phase 6 | Pending |
| CLOSE-04 | Phase 6 | Pending |
| CLOSE-05 | Phase 6 | Pending |
| CLOSE-06 | Phase 6 | Pending |
| LIVE-04 | Phase 7 | Pending |
| AN-01 | Phase 7 | Pending |
| AN-02 | Phase 7 | Pending |

**Coverage:**
- v1.1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-22*
*Last updated: 2026-04-22 — traceability filled by roadmapper (12/12 requirements mapped to Phases 5-7)*
