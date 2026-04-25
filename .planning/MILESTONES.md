# Milestones

## v1.1 Live Validation (Shipped: 2026-04-25)

**Goal:** Transition from "ships clean code" to "actually used weekly for 5-10 US equity positions" — with signal noise surfaced, triaged, and actionable, not buried in preliminary-calibration flags.

**Scope:** 3 phases · 8 plans · 16 tasks · 12/12 v1.1 requirements

**Timeline:** 2026-04-23 → 2026-04-25 (3 calendar days, single autonomous-mode session continued from v1.0).

### Key accomplishments

- **Phase 5 — Corpus Population + Live Data Closeout (LIVE-01, CLOSE-01..03):** `POST /api/v1/calibration/rebuild-corpus` async endpoint with `corpus_rebuild_jobs` table, per-ticker FOUND-07 single-element delegation, outer exception guard + `error_message` population (WR-01/WR-02 fixes); 3 v1.0 human-UAT items closed via pytest skipif-guarded suites + operator CLI scripts — FinBERT lazy-import contract via `importlib.util.find_spec`, Finnhub live round-trip + `FundamentalAgent` reasoning marker, daemon subprocess PID lifecycle + cross-platform atexit cleanup.
- **Phase 6 — Calibration & Weights UI (LIVE-02, LIVE-03, CLOSE-04..06):** `agent_weights` table + 3 endpoints (`GET /weights`, `POST /weights/apply-ic-ir`, `PATCH /weights/override`) with `KNOWN_AGENTS` allowlist (5 agents — `SummaryAgent` excluded per WR-01); unified `/calibration` page combining LIVE-02 (per-agent Brier/IC/IC-IR + 90-day rolling-IC sparkline + FOUND-04 note for FundamentalAgent) and LIVE-03 (WeightsEditor with current vs IC-IR-suggested + Apply button + per-agent exclude toggle); 3 v1.0 browser-UAT items closed via Vitest snapshot tests + operator scripts; CalibrationPage `setTimeout` cancellation on unmount (WR-02).
- **Phase 7 — Digest + Analytics Completeness (LIVE-04, AN-01, AN-02):** `engine/digest.py` weekly Markdown renderer with 5 H2 sections (perf vs benchmark, signal flips, IC-IR movers, thesis-drift alerts, action items) + Sunday 18:00 APScheduler cron + `EmailDispatcher.send_markdown_email` (HTML-escaped + `<pre>`-wrapped) + PII clamp (no $ amounts, no thesis text via `\b(thesis|secret)\b.*` regex per WR-03); dividend-aware `compute_irr_multi(dividends=...)` with `YFinanceProvider.get_dividends` + `DividendCache` Parquet sibling (FOUND-02 pattern, 24h TTL); `engine/drift_detector.py` with `MIN_SAMPLES_FOR_REAL_THRESHOLD=60` preliminary flag, `>20%` drop or `<0.5` floor triggers, `_apply_drift_scale` UPSERT preserving `manual_override=1` (WR-02), NEVER-zero-all guard, Sunday 17:30 cron, `drift_log` table; `DriftBadge.tsx` 3-state UI integrated into `CalibrationPage`; **closed Phase 6 deferred pipeline wiring** — `engine/pipeline.py::analyze_ticker` now reads `load_weights_from_db` so daemon analysis honors persisted weights.

### Stats

- **Commits:** 56 across 3 phases (research → plan → execute × 8 plans → review → review-fix × 3 phases → verify → complete) — all on `main` per `branching_strategy: none`
- **Files changed:** 143 files; +22,598 / −707 LOC since `v1.0` tag
- **Tests:** ~970 backend + frontend total; 0 regressions; 5 expected pytest skips for live-credential CLOSE-01/02 tests (meta-tests verify the skipif guards exist)
- **Code reviews:** 3 REVIEW.md + 3 REVIEW-FIX.md reports; 0 critical blockers shipped; 6 warnings caught and fixed mid-phase (Phase 6 WR-01 SummaryAgent allowlist + WR-02 setTimeout-on-unmount; Phase 7 WR-01 threshold_type literal mismatch + WR-02 manual_override renorm denominator + WR-03 over-redacted "position" in PII clamp)
- **Most dangerous bug caught:** Phase 6 WR-01 — `SummaryAgent` was in `KNOWN_AGENTS` allowlist for weight overrides; SummaryAgent is the meta-aggregator (signals weighted-summed inside it), so allowing weight overrides on it would have created a feedback loop. Removed before any frontend tested against it.
- **Most consequential silent bug fixed:** Phase 7 WR-02 — `_apply_drift_scale` SELECT included `manual_override=1` rows in the renormalization denominator but the UPSERT skipped them, producing scaled weights that wouldn't sum to 1.0 and silently violating FOUND-05. Fixed by adding `AND manual_override = 0` to the SELECT.

### Verification debt carried forward (8 deferred operator items)

All v1.1 phases closed with operator-runtime UAT items that cannot be automated without external services:

- **Phase 5 (1 item):** Live corpus rebuild against operator's actual portfolio (multi-minute YFinance fetch).
- **Phase 6 (4 items):** Apply IC-IR weights live round-trip; CLOSE-04 target-weight browser persistence on reload; CLOSE-05 rules panel daemon-log verification; CLOSE-06 DailyPnlHeatmap native-tooltip on hover.
- **Phase 7 (3 items):** Live SMTP email delivery of weekly digest; non-preliminary drift detection (requires 60+ weekly IC samples per agent — corpus accumulation over multiple months); `CalibrationPage` DriftBadge visual verification in real browser.

Tracked in `05-HUMAN-UAT.md`, `06-HUMAN-UAT.md`, `07-HUMAN-UAT.md`.

### Known residuals (deferred to v1.2+)

- v1.0 deferred items still standing: position-lifecycle fragmentation, `pandas_ta` FutureWarnings, `error_message` scrubbing, dividends-in-IRR was AN-01 (now CLOSED), TradeNote journal depth.
- New v1.1 deferred: `_clamp_pii` regex narrowness vs alert content (intentionally narrow per WR-03 fix); `email_dispatcher.send_markdown_email` uses simple `html.escape()` + `<pre>` wrap rather than full Markdown→HTML rendering; drift detector thresholds (`>20%` / `<0.5`) are reasonable priors not yet back-tested against live corpus (research flag carried into v1.2).

### Archived artifacts

- `.planning/milestones/v1.1-ROADMAP.md` — full milestone roadmap snapshot
- `.planning/milestones/v1.1-REQUIREMENTS.md` — final 12/12 requirements with outcomes
- `.planning/milestones/v1.1-phases/0{5,6,7}-*/` — per-phase PLAN + SUMMARY + REVIEW + REVIEW-FIX + VERIFICATION + HUMAN-UAT files

---

## v1.0 Competitive Parity (Shipped: 2026-04-22)

**Goal:** Survey the OSS investment-agent ecosystem, identify gaps vs. competitors, and ship the borrowable improvements — hardening the existing brownfield system against liabilities, then layering calibrated signal quality, expanded free-tier data, and a UI/analytics uplift that closes the table-stakes gap vs. Ghostfolio and Portfolio Performance.

**Scope:** 4 phases · 14 plans · 22 tasks · 25/25 v1 requirements

**Timeline:** Research + planning + execution completed in a single session on 2026-04-22.

### Key accomplishments

- **Phase 1 — Foundation Hardening (FOUND-01..07):** yfinance batch download + Parquet OHLCV cache with Windows-safe atomic writes; `arch.optimal_block_length()` auto-selecting Monte Carlo block size; `backtest_mode` flag preventing FundamentalAgent look-ahead bias; 12-scenario parametrized weight-renormalization test; SQLite WAL + covering indexes + 90-day `signal_history` pruning; `job_run_log` four-state audit + atomic BEGIN/COMMIT/ROLLBACK + startup crash reconciliation.
- **Phase 2 — Signal Quality Upgrade (SIG-01..06):** QuantStats historical-simulation CVaR (95/99%) replacing Gaussian approximation, with matplotlib-leak regression guard; portfolio-level VaR; one-vs-rest Brier score + time-series Pearson IC/IC-IR per agent; IC-IR-based weight scaling (negative IC → zero weight); transaction costs in backtester (10 bps equities / 25 bps crypto); walk-forward scaffold (30-day train / 10-day OOS, purge=5 for IC-feeding, purge=1 for Sharpe-only); `backtest_signal_history` corpus with atomic rollback.
- **Phase 3 — Data Coverage Expansion (DATA-01..05):** Finnhub provider with peer-basket sector P/E (60/min rate limit); FinBERT local sentiment fallback (`[llm-local]` optional extra, lazy-import safe); SEC EDGAR Form 4 insider signal via `edgartools`; stdlib JSON-formatted logging + `GET /health` reading `job_run_log`; daemon PID file + cross-platform stale detection + API/uvicorn pinned to `127.0.0.1`.
- **Phase 4 — Portfolio UI + Analytics Uplift (UI-01..07):** TTWROR + IRR (scipy.brentq for multi-cashflow) + benchmark overlay with SSRF-safe allowlist; daemon-wired alert rules with "Built-in" badge; target-weight column + `TargetWeightBar` frontend component; daily P&L calendar heatmap (custom SVG + Tailwind, keyboard-accessible); `PositionStatus` FSM with `VALID_TRANSITIONS` dict; opt-in Bull/Bear LLM synthesis with FOUND-04 backtest-mode short-circuit as the FIRST check (prevents ~$2.78/ticker runaway cost on backtests).

### Stats

- **Commits:** ~95 over a single session (codebase mapping → research → requirements → roadmap → 4 phases × (plan + execute + review + review-fix + verify + complete))
- **Tests:** ~910 total (backend pytest + frontend Vitest), 0 regressions across phases
- **Code reviews:** 4 REVIEW.md + 4 REVIEW-FIX.md reports. 0 critical blockers shipped; 2 critical findings + 15 warnings caught and fixed mid-phase
- **Most dangerous bug caught:** Phase 2 WR-01 — `populate_signal_corpus` read `raw_score` from per-agent sub-dicts where the field didn't exist; every corpus row had `NULL`, silently breaking IC computation. Fixed post-review before Phase 3 depended on it.
- **Most expensive bug prevented:** Phase 4 UI-07 — LLM synthesis `backtest_mode` short-circuit ordered as the FIRST check (before ENABLE_LLM_SYNTHESIS, before API key). Research warned missing this would have cost ~$2.78/ticker on a 3-year daily backtest.

### Verification debt carried forward

- **Phase 3 human-UAT (3 items):** live FinBERT on real headlines (requires `[llm-local]` install), live Finnhub API round-trip (requires `FINNHUB_API_KEY`), daemon PID + `netstat 127.0.0.1` live confirmation.
- **Phase 4 human-UAT (3 items):** target-weight deviation bar browser flow, MonitoringPage rules panel toggle-then-curl, DailyPnlHeatmap tooltip.

Run `/gsd-verify-work 3` and `/gsd-verify-work 4` to close out these items post-ship.

### Known residuals (deferred to v1.x)

From `.planning/codebase/CONCERNS.md` (pre-existing) and Phase 2-4 review notes:

- Position lifecycle fragmented across `active_positions`, `trade_records`, `signal_history` — Phase 4 FSM is a start but full event-sourcing deferred
- `pandas_ta` FutureWarnings on Pandas 3.x — waiting on upstream or `pandas-ta-classic` migration (DEPLOY-v2-03)
- `error_message` in `job_run_log` stores raw `str(exc)` — scrubbing deferred
- `signal_history` only 10 rows — needs extended operation or backfill before live Brier/IC calibration is meaningful
- Dividends not tracked in IRR — documented in Phase 4 Plan 04-01 risks
- TradeNote-style journal psychology features — `JournalPage.tsx` covers core; deeper features deferred to UI-v2

### Archived artifacts

- `.planning/milestones/v1.0-ROADMAP.md` — full milestone roadmap snapshot
- `.planning/milestones/v1.0-REQUIREMENTS.md` — final requirements with outcomes
- `.planning/phases/0{1,2,3,4}-*/` — per-phase PLAN + SUMMARY + REVIEW + REVIEW-FIX + VERIFICATION files (still in place; phase archival is optional)

---
