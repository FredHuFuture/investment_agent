# Roadmap: Investment Agent

---

## v1.0 Competitive Parity (Archived — Shipped 2026-04-22)

All 4 phases complete. Full snapshot in `.planning/milestones/v1.0-ROADMAP.md`.

| Phase | Goal | Status |
|-------|------|--------|
| 1 - Foundation Hardening | Infrastructure correctness: yfinance batch, WAL, atomic daemon, backtest_mode | Complete |
| 2 - Signal Quality Upgrade | Calibrated signal quality: CVaR, Brier, IC/IC-IR, walk-forward, transaction costs | Complete |
| 3 - Data Coverage Expansion | Free-tier providers + operator observability: Finnhub, FinBERT, EDGAR, /health, PID | Complete |
| 4 - Portfolio UI + Analytics Uplift | Table-stakes UI: TTWROR/IRR, benchmark overlay, heatmap, alert rules panel, LLM synthesis | Complete |

---

## v1.1 Live Validation (Current Milestone)

**Milestone goal:** Transition from "ships clean code" to "actually used weekly for 5-10 US equity positions" — with signal noise surfaced, triaged, and actionable.

**Operating context:**
- Cadence: weekly review + research (not daily, not alert-driven)
- Universe: 5-10 US equity tickers
- Top rough edge: signal noise — calibration visibility is the north star
- Phase numbering continues from v1.0 (starts at 5)

## Phases

- [x] **Phase 5: Corpus Population + Live Data Closeout** - Populate the real signal corpus for user's tickers and verify all three v1.0 live-environment UAT items that could not be automated
 (completed 2026-04-23)
- [ ] **Phase 6: Calibration & Weights UI** - Surface per-agent signal quality visually and give the user a one-click path to apply IC-IR-derived weights; close out v1.0 browser UAT items
- [ ] **Phase 7: Digest + Analytics Completeness** - Weekly review artifact, dividend-accurate IRR, and a drift detector that auto-scales weights when an agent loses edge

## Phase Details

### Phase 5: Corpus Population + Live Data Closeout
**Goal**: The calibration corpus exists for all user-configured tickers with 3+ years of signal history, and all three live-environment v1.0 UAT items are documented as resolved — so Phase 6 UI has real data to display and there are no "partial" verification debts hanging over live data infrastructure.
**Depends on**: Nothing (builds directly on v1.0 foundation — `rebuild_signal_corpus`, `job_run_log`, Finnhub provider, FinBERT, and daemon PID all shipped in v1.0 Phases 2-3)
**Requirements**: LIVE-01, CLOSE-01, CLOSE-02, CLOSE-03
**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/analytics/calibration` returns non-zero `sample_size` for all non-Fundamental agents across at least 5 user-configured US equity tickers, with corpus `date_range` spanning at least 3 years prior to today — verifiable by calling the endpoint and inspecting the JSON response.
  2. `POST /api/v1/calibration/rebuild-corpus` triggers `rebuild_signal_corpus` for each ticker in the user's portfolio, returns a progress response (ticker count or completion status), and completes without error — verifiable by issuing the POST and then calling the calibration endpoint to confirm updated row counts.
  3. FinBERT live test documented: running `pip install -e ".[llm-local]"` + the FinBERT fetch script and analyzing a news-rich ticker (NVDA earnings week) with `ANTHROPIC_API_KEY` unset returns a non-HOLD signal with FinBERT-sourced reasoning — result documented in `03-HUMAN-UAT.md` with status flipped from `partial` to `resolved`.
  4. Finnhub live test documented: setting a real `FINNHUB_API_KEY` and calling `FinnhubProvider.get_sector_pe("technology")` returns a non-None float, and `FundamentalAgent` reasoning on AAPL contains the string `"Finnhub sector P/E"` — result documented in `03-HUMAN-UAT.md`.
  5. Daemon PID test documented: launching the daemon writes `data/daemon.pid` with a live PID matching the running process, `netstat -an` shows `127.0.0.1:8000 LISTEN` (not `0.0.0.0`), and killing the daemon removes the PID file via atexit — result documented in `03-HUMAN-UAT.md`.
**Plans**: 2 plans
  - [x] 05-01-PLAN.md (wave 1) — LIVE-01: Corpus rebuild backend endpoint + background task + progress API (`POST /analytics/calibration/rebuild-corpus` + `GET .../{job_id}` + `corpus_rebuild_jobs` table)
  - [x] 05-02-PLAN.md (wave 1) — CLOSE-01..03: Three live-environment UAT closeouts (FinBERT / Finnhub / daemon-PID tests + operator scripts + `03-HUMAN-UAT.md` update to `resolved`)

### Phase 6: Calibration & Weights UI
**Goal**: The user can open a browser, see which agents are performing well or poorly this week (Brier, IC, IC-IR, sparkline), apply IC-IR-suggested weights with one click, manually disable a noisy agent, and confirm the three deferred v1.0 browser-side UAT flows work as intended — so the dashboard is genuinely usable as a weekly review surface.
**Depends on**: Phase 5 (corpus must be populated for calibration metrics to be non-null; otherwise every cell shows "insufficient data")
**Requirements**: LIVE-02, LIVE-03, CLOSE-04, CLOSE-05, CLOSE-06
**Success Criteria** (what must be TRUE):
  1. Visiting `/calibration` renders a table with one row per agent (Technical, Macro, Crypto, Sentiment) showing Brier score, rolling IC, IC-IR, and a 90-day sparkline trend — the FundamentalAgent row is present but displays the FOUND-04 explanatory note ("excluded from backtest corpus") instead of null metrics — verifiable by loading the page against a populated corpus.
  2. Visiting `/weights` (or the weights section of CalibrationPage) shows current agent weights alongside IC-IR-suggested weights; clicking "Apply IC-IR weights" persists the new weights to the `agent_weights` table — the next daemon `signal_aggregator` run uses the updated weights, verifiable by diffing daemon log output before and after applying.
  3. The per-agent manual override toggle persists an "excluded" state for a chosen agent; the next analysis run omits that agent's signal and the remaining agents' weights re-normalize to sum to 1.0 — verifiable by inspecting the aggregation log entry.
  4. Target-weight browser flow verified: set target weight, bar renders with correct deviation color, persists on page reload, clearing sets to null, out-of-range value shows validation alert — documented in `04-HUMAN-UAT.md` with status `resolved`.
  5. Rules panel toggle verified (STOP_LOSS_HIT off → next daemon monitor log excludes it → re-enabling restores it) and DailyPnlHeatmap tooltip verified (hover shows correct date and P&L) — both documented in `04-HUMAN-UAT.md` with status `resolved`.
**Plans**: 3 plans
  - [ ] 06-01-PLAN.md (wave 1) — LIVE-03 backend: `agent_weights` table + 3 endpoints (GET /weights overview, POST /weights/apply-ic-ir, PATCH /weights/override) + SignalAggregator DB wiring
  - [ ] 06-02-PLAN.md (wave 2, depends_on: [06-01]) — LIVE-02 + LIVE-03 frontend: `/calibration` page with per-agent Brier/IC/IC-IR/sparkline + embedded WeightsEditor (Current vs IC-IR-suggested + exclude toggle + Apply button)
  - [ ] 06-03-PLAN.md (wave 2) — CLOSE-04..06 UAT closeout: 3 Vitest snapshot tests + 3 operator scripts + `04-HUMAN-UAT.md` flip to resolved
**UI hint**: yes

### Phase 7: Digest + Analytics Completeness
**Goal**: The user receives (or can trigger on demand) a weekly Markdown digest that surfaces the week's key portfolio signals in one artifact; dividend-paying positions report accurately higher IRR; and a drift detector automatically flags and down-weights agents whose IC-IR has degraded — so the weekly review workflow is self-contained and signal trust is maintained without manual intervention.
**Depends on**: Phase 5 (corpus populated — digest IC-IR movers require non-null corpus data), Phase 6 (weights UI in place — drift detector writes to the same `agent_weights` table and surfaces a badge in CalibrationPage)
**Requirements**: LIVE-04, AN-01, AN-02
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/digest/weekly` returns a Markdown body containing all five sections: (a) portfolio performance vs benchmark this week, (b) top 5 signal flips, (c) agents whose IC-IR moved more than 20% from their 60-day average, (d) open thesis drift alerts, (e) action items — verifiable by calling the endpoint and confirming all five section headers appear in the response body.
  2. The weekly digest APScheduler job runs at Sunday 18:00 (verifiable from `job_run_log` showing a `digest_weekly` job with `started_at` timestamped in the Sunday 18:00 window), and opt-in email delivery sends the Markdown body via the existing notification channel when `SMTP_*` env vars are configured.
  3. `compute_irr_multi` called with a `dividends` parameter containing at least one `(date, amount)` tuple returns a strictly higher IRR than the same call with an empty list for a test position in a dividend-paying stock (MSFT or KO) — verifiable by the test suite and inspecting the `GET /analytics/returns` response for a portfolio containing such a position.
  4. `engine/drift_detector.py` evaluates per-agent IC-IR weekly; when IC-IR drops more than 20% below its 60-day rolling average OR falls below 0.5 for two consecutive weekly runs, it emits an alert via the existing notification channel AND writes a scaled-down weight to the `agent_weights` table via WeightAdapter — verifiable by inspecting `agent_weights` rows before and after a simulated IC-IR drop.
  5. The CalibrationPage shows a "drift detected" warning badge on any agent row where the drift detector has flagged degradation within the last 7 days — verifiable by triggering a drift condition (via test fixture or manual threshold injection) and loading `/calibration`.
**Plans**: TBD
**UI hint**: yes

---

## Progress

**Execution order:** 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 5. Corpus Population + Live Data Closeout | 2/2 | Complete    | 2026-04-23 |
| 6. Calibration & Weights UI | 0/3 | Not started | - |
| 7. Digest + Analytics Completeness | 0/TBD | Not started | - |

---

## Research Flags

- **Phase 7 (AN-02 drift detector):** Threshold calibration needs validation — the ">20% below 60-day average" and "IC-IR < 0.5 for 2 consecutive weeks" thresholds are reasonable priors but have not been back-tested against the live corpus. Flag for `/gsd-research-phase 7` if the planner cannot determine appropriate thresholds from existing signal data at planning time.
- **Phase 6 (WeightsPage UI):** Phase 4 research established Recharts + custom-SVG stack. Reuse that stack — no new research needed.

---

## v1.2+ Placeholder

Next milestone candidates (not yet scoped):
- Docker + docker-compose deployment story (DEPLOY-v2-01)
- OpenTelemetry + Prometheus metrics (DEPLOY-v2-02)
- `pandas-ta-classic` migration (DEPLOY-v2-03)
- Allocation donut charts, CSV import wizard, alert-threshold UI (UI-v2-01..03)
- Riskfolio-Lib position sizing, QuantStats tearsheet (UI-v2-04..05)
- Signal Quality v2: calibration reliability plots, adaptive RSI, MarketAux, SimFin (SIG-v2-*, DATA-v2-*)
