# Milestones

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
