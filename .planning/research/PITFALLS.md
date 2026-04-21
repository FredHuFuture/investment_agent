# Architecture & Deploy Story — Pitfalls Research

**Domain:** OSS Investment Agents / Trading Bots / AI-Finance (local-first, single-user)
**Researched:** 2026-04-21
**Confidence:** MEDIUM-HIGH (critical claims verified against project issues, official docs, and OSS source)
**Scope:** Competitive survey of 15+ OSS projects; mapped to our brownfield codebase

---

## OSS Landscape Summary

Projects surveyed (with GitHub URLs):

| Project | Stars approx | Language | Architecture Pattern | DB | Scheduler |
|---------|-------------|----------|---------------------|----|-----------|
| [freqtrade](https://github.com/freqtrade/freqtrade) | 35k+ | Python | Modular monolith + event loop | SQLite → Postgres | Internal clock + APScheduler-style |
| [nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | 4k+ | Rust+Python | Actor / single-threaded kernel, DDD | Redis (optional) + DataFusion | Message-bus event dispatch |
| [OpenBB](https://github.com/OpenBB-finance/OpenBB) | 35k+ | Python | Modular provider platform | None (data-broker only) | Request-driven, no scheduler |
| [ai-hedge-fund (virattt)](https://github.com/virattt/ai-hedge-fund) | 30k+ | Python | LangGraph multi-agent, CLI-first | None (logs only) | None — manual invocation |
| [TradingAgents (TauricResearch)](https://github.com/TauricResearch/TradingAgents) | 6k+ | Python | LangGraph multi-agent | None | None |
| [Hummingbot](https://github.com/hummingbot/hummingbot) | 9k+ | Python+Cython | Clock-driven event loop + connector adapters | None persistent | Clock ticks (1s default) + Cython hot path |
| [lumibot](https://github.com/Lumiwealth/lumibot) | 2k+ | Python | Strategy lifecycle loop | Parquet local / S3 optional | Backtest bar-by-bar loop |
| [jesse](https://github.com/jesse-ai/jesse) | 6k+ | Python | Modular framework | Undisclosed (Docker) | None explicit (CLI batch) |
| [FinRL](https://github.com/AI4Finance-Foundation/FinRL) | 10k+ | Python | RL environment layers | None | None — training loops |
| [qlib (Microsoft)](https://github.com/microsoft/qlib) | 15k+ | Python | Client/server, WebSocket data bus | Custom data store (bcolz) | Flask-SocketIO server |
| [zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) | 1k+ | Python | Event-driven backtest loop | SQLite (metadata) + bcolz | Trading-calendar clock |
| [backtrader](https://github.com/mementum/backtrader) | 15k+ | Python | Event-driven strategy loop | None | Custom bar clock |
| [vectorbt](https://github.com/polakowo/vectorbt) | 4k+ | Python | Vectorized NumPy/Numba | None | None |

**Our project:** Layered async monolith — FastAPI + APScheduler daemon + SQLite (aiosqlite) + six-agent pipeline + React frontend.

---

## Critical Pitfalls

### Pitfall 1: yfinance Global Lock Serializes All Downloads — Silent Throughput Cap

**Priority:** HIGH

**What goes wrong:**
`yfinance.download()` is not thread-safe. A shared global `_DFS` dictionary is written to by concurrent calls without locks, causing race conditions and silent data overwrites when the same ticker is fetched with different parameters concurrently. Our workaround (`_yfinance_lock` in `data_providers/yfinance_provider.py`) is correct but complete serialization: every download waits for the global lock regardless of ticker, creating a hard ~2 calls/second ceiling. At 100+ tickers, backtest downloads take 50+ seconds before any analysis runs.

**Competitor comparison:**
- **freqtrade** sidesteps this entirely by using its own `download-data` CLI command that saves to local disk first, then backtests against local files — zero live yfinance calls during backtesting runs.
- **lumibot** uses local Parquet caches and optionally mirrors to S3; yfinance is used only for the initial cache fill, not during strategy execution.
- **vectorbt** integrates `yfinance.download()` but wraps it in its own chunking layer and expects callers to pre-download data as a batch.
- **nautilus_trader** avoids the problem entirely via adapter abstraction and does not use yfinance.
- yfinance issue [#2557](https://github.com/ranaroussi/yfinance/issues/2557) (opened June 2025, unresolved): "Since `_DFS` is a global dictionary, two threads downloading the same ticker with different parameters may overwrite each other's results before the final result is returned to callers."

**Our current state:**
`data_providers/yfinance_provider.py` lines 15-16, 33-40, 73 — `threading.Lock()` held across full download+parse cycle. Lock held across `yfinance.download()` + DataFrame normalization = serialized. No local Parquet/DuckDB cache; every backtest tick re-fetches. `CONCERNS.md`: "Rate-limited to 2 calls/second globally; backtesting with many tickers (100+) becomes very slow."

**Warning signs:**
- Backtest duration scales linearly (not O(log n)) with ticker count.
- `asyncio.gather()` on pipeline doesn't help throughput for equity analysis — all paths converge on the same lock.
- Users report "analysis slow for large portfolios" — root is the download serialization, not agent compute.
- `429 Too Many Requests` from Yahoo Finance when rapid sequential calls exceed the undocumented ceiling.

**Prevention strategy:**
1. **Phase 1 (quick win):** Implement a local Parquet cache layer. On first fetch, write DataFrame to `data/cache/{ticker}_{period}_{interval}.parquet`. Re-reads bypass yfinance entirely for TTL window.
2. **Phase 2 (structural fix):** Adopt freqtrade's separation: a `prefetch_data` daemon job downloads all portfolio tickers in batch (using `yfinance.download(tickers, group_by='ticker')` which supports multi-ticker in one call, reducing HTTP round-trips), persists to disk, and the analysis pipeline reads from disk only.
3. **Phase 3 (longer term):** Add a provider-agnostic `MarketDataStore` class wrapping Parquet/DuckDB for historical queries — provider can be swapped to polygon.io or Finnhub without pipeline changes.

**Phase to address:** Phase 1 (data layer hardening) — before adding more tickers to watchlist or expanding backtest scope.

---

### Pitfall 2: APScheduler 3.x Job State Lost on Crash — No Recovery Guarantee

**Priority:** HIGH

**What goes wrong:**
APScheduler 3.x in-memory scheduler (`AsyncIOScheduler`) loses all scheduled job state on process crash. If the daemon process dies mid-job (e.g., during daily analysis with 20 positions), no audit trail exists of partial execution. Jobs that started writing signals to the database but did not complete leave orphaned signal rows. Re-start re-runs the job at its next scheduled interval rather than replaying the missed run, causing a silent gap in monitoring history.

A secondary failure mode: running FastAPI with multiple Uvicorn workers causes APScheduler to spawn N scheduler instances, one per worker, leading to duplicate job execution. (Source: [APScheduler issue #499](https://github.com/agronholm/apscheduler/issues/499) — `SQLAlchemyJobStore` `OperationalError` when `apscheduler_jobs` table already exists during process reload.)

**Competitor comparison:**
- **freqtrade** runs its scheduler in a single dedicated process (not embedded in the web API process), avoiding the multi-worker duplication problem. Trade state is checkpointed to SQLite atomically after each decision.
- **nautilus_trader** uses a crash-only design: on unrecoverable error, the process aborts immediately and a supervisor (systemd, Docker restart policy) brings it back. State is externalized to Redis or disk before abort.
- **Hummingbot** uses a Clock singleton with deterministic tick ordering; state is in-memory but the Clock's sequential dispatch prevents partial-write gaps within a tick.

**Our current state:**
`daemon/scheduler.py` — `MonitoringDaemon` with `AsyncIOScheduler`. `daemon/jobs.py` has broad `try/except` that catches all exceptions and logs them, swallowing partial DB transaction failures. `CONCERNS.md`: "Daemon job exception handling — swallows subtle bugs (e.g., partial DB transaction failure where some rows written, some not)."

**Warning signs:**
- `daemon/jobs.py` job function completes without error but database has partial signal set (fewer rows than expected positions).
- Process restart logs show job ran at unexpected intervals (was missed or doubled).
- Two Uvicorn worker processes both write signals for the same position on the same day.
- Alert dispatched without corresponding signal record in DB.

**Prevention strategy:**
1. **Immediate:** Add a `job_run_log` table with (job_name, started_at, completed_at, status). Each job writes `started_at` at entry; writes `completed_at` + `status='success'` only on clean completion. Re-start checks for `status='running'` rows and marks them `'aborted'` for manual triage.
2. **Isolate daemon from API process:** Run `python -m daemon.scheduler` as a separate process (already possible via `daemon_cli.py`) with systemd or Docker restart policy — do not embed in Uvicorn workers.
3. **Atomic job transactions:** Wrap each job's DB writes in a single `async with conn` transaction block; commit at end or rollback on exception. Replace `except Exception: log()` with `except NetworkError: retry()` / `except DBError: raise` pattern.
4. **APScheduler 4.x migration (deferred):** APScheduler 4.x rewrites job concept as Task + Schedule + Job with persistent data stores, but is still pre-release as of April 2026. Pin to 3.x until 4.x reaches stable.

**Phase to address:** Phase 1 (reliability hardening) — before adding observability; a missing job log makes it impossible to distinguish "job ran but found nothing" from "job crashed."

---

### Pitfall 3: SQLite Single-Writer Bottleneck Under Concurrent Daemon + API Load

**Priority:** HIGH

**What goes wrong:**
SQLite in WAL mode supports unlimited concurrent readers but exactly one writer at a time. When the daemon's daily analysis job is writing 20+ signal rows while the API is concurrently handling portfolio update requests, write contention causes `OperationalError: database is locked` failures or multi-second latency spikes. With a large signal history table (no pruning), query scans are also slow.

Freqtrade's [issue #6791](https://github.com/freqtrade/freqtrade/issues/6791) documents: "Unrealistically high CPU usage of freqtrade when frequi is run with a large SQLite database." Resolution: migrate to PostgreSQL for any production instance with substantial data.

**Competitor comparison:**
- **freqtrade** uses SQLite for single-instance operation but officially recommends PostgreSQL for `--db-url` when running with the FreqUI web dashboard simultaneously.
- **jesse** isolates backtesting from live operation — different data paths, no shared writer contention.
- **nautilus_trader** externalizes state to Redis (in-memory) or DataFusion (analytical queries) — no SQLite WAL contention.
- **zipline-reloaded** uses SQLite only for bundle metadata (small, infrequent writes); OHLCV data lives in bcolz columnar format.

**Our current state:**
`db/connection_pool.py` — async SQLite connection pool with `aiosqlite`. WAL mode likely enabled (standard for aiosqlite). `CONCERNS.md`: "SQLite single-writer constraint — 100+ concurrent requests saturate sqlite WAL lock." Signal history table grows 50-100 rows/day with no pruning. No indexes on `(portfolio_id, timestamp)` on `portfolio_snapshots`.

**Warning signs:**
- `OperationalError: database is locked` in API logs during daemon job window (typically the daily analysis cron).
- Portfolio analytics page slow to load (>3s) when signal history table exceeds ~50k rows.
- Daemon jobs extend past their scheduled interval, causing overlap with next scheduled run.
- `PRAGMA wal_checkpoint` stalls visible in SQLite profiling.

**Prevention strategy:**
1. **Immediate (Phase 1):** Enable `PRAGMA journal_mode=WAL` explicitly, `PRAGMA synchronous=NORMAL`, `PRAGMA wal_autocheckpoint=1000`. Add index `CREATE INDEX IF NOT EXISTS idx_snapshots_pid_ts ON portfolio_snapshots(portfolio_id, timestamp)`. Add index on `signal_history(ticker, created_at)`.
2. **Pruning (Phase 1):** Add a weekly cleanup job in `daemon/jobs.py` that archives signal rows older than 90 days to `signal_history_archive` table. Keeps active table small.
3. **Scaling path (Phase 3+):** When portfolio > 200 positions or concurrent users > 1, migrate to PostgreSQL via ORM-neutral schema (schemas are already written in raw SQL in `db/database.py` — port is straightforward).

**Phase to address:** Phase 1 (reliability) for indexes and pruning; Phase 3 for Postgres migration decision.

---

### Pitfall 4: Look-Ahead Bias in Fundamental Backtests — yfinance Returns Restated Data

**Priority:** HIGH (for backtest validity)

**What goes wrong:**
`yfinance` financials endpoints return the most recently reported (and potentially restated) data, not what was available at the point in time being backtested. A backtest run in 2026 covering 2022 will use 2022 earnings figures as revised in 2023, 2024, or 2025. For fundamental signals (P/E, earnings growth, debt ratios), this can shift BUY/SELL signals materially. Academic research on the memorization problem in LLM-based trading (Lopez-Lira et al., 2024) further notes that LLMs can recall exact historical prices within their training window, compounding look-ahead bias in AI-assisted backtests.

**Competitor comparison:**
- **zipline-reloaded** explicitly designed around this: pipeline API enforces a `as_of_date` parameter and Quantopian's data bundles include point-in-time fundamental data.
- **freqtrade** avoids fundamental data entirely — signals are technical only; look-ahead bias manifests only in indicator computation (which it catches with `lookahead-analysis` CLI tool — see [freqtrade docs](https://www.freqtrade.io/en/stable/lookahead-analysis/)).
- **qlib (Microsoft)** built point-in-time data handling as a core feature via its `DataHandler` class which stores release-date metadata.
- **FinRL-X** acknowledges the "research-to-production gap" and attempts to unify offline evaluation and live deployment, but does not solve fundamental data look-ahead itself.

**Our current state:**
`backtesting/data_slicer.py` — time-slices price history for point-in-time accuracy on prices. `agents/fundamental.py` calls `yfinance` for current financials without point-in-time guardrail. `CONCERNS.md`: "FundamentalAgent uses yfinance which provides current/restated financials. Backtesting results are overfitted (used future data). Priority: High for backtesting confidence."

**Warning signs:**
- Backtest Sharpe ratio significantly higher than forward walk-forward test on same strategy.
- Fundamental signals in backtest show BUY on stocks that were visibly distressed at the time (e.g., high P/E restatement post-earnings fraud).
- `FundamentalAgent` called inside `backtesting/engine.py` without a `point_in_time` flag or date override.

**Prevention strategy:**
1. **Immediate (Phase 1):** Add a `backtest_mode: bool` flag to `AgentInput`. When `True`, `FundamentalAgent.analyze()` returns HOLD with a warning ("Fundamental data not point-in-time in backtest mode") rather than using restated yfinance data.
2. **Medium term (Phase 2):** Integrate a free point-in-time proxy: Financial Modeling Prep (FMP) free tier provides quarterly SEC filing data with filing dates. Or: use `yfinance` quarterly earnings history (`ticker.earnings_history`) where `reportDate` field provides a proxy for when data was available.
3. **Longer term (Phase 3+):** Evaluate Norgate or FMP premium ($20-50/month) for reliable point-in-time fundamentals if backtest accuracy becomes a product differentiator.

**Phase to address:** Phase 1 (flag to suppress in backtest) is a quick correctness fix. Phase 2 for a real solution.

---

### Pitfall 5: Position Lifecycle Fragmented Across Tables — Join Complexity Grows Exponentially

**Priority:** HIGH (tech debt risk)

**What goes wrong:**
As new features touch position data (thesis drift, signal correlation, performance attribution, journal), each new table that references position state adds another join to any comprehensive query. With three tables today (`active_positions`, `trade_records`, `signal_history`), queries for "what signals did we have when we entered this position" already require 3-way joins. Adding journal entries, export data, and attribution creates N-way joins that are fragile under schema changes and difficult to test.

Freqtrade hit this exact wall with its early schema: trades, orders, and pair locks were in separate tables, causing cascading failures when a trade was partially filled. Their [2021 database migration](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/persistence/migrations.py) introduced a unified `Order` model linked to `Trade` with a clear lifecycle FSM (`open → partial_fill → closed / cancelled`).

**Competitor comparison:**
- **nautilus_trader** models all lifecycle events as immutable domain events (`OrderInitialized`, `OrderFilled`, `OrderCanceled`) stored in an event log — the current state is a projection of events, not a mutable row. No join ambiguity because state is reconstructed from the event stream.
- **freqtrade** settled on a `Trade` model with embedded `Order` list and explicit `is_open` / `close_date` fields, plus FSM validation in Python. Migration history is in `persistence/migrations.py`.
- **Hummingbot** tracks order state via a deterministic Clock tick — position state is always consistent because writes only happen inside the Clock's dispatch sequence (no concurrent writers).

**Our current state:**
`db/database.py` — `active_positions`, `trade_records`, `signal_history`, `positions_thesis` are separate tables with FKs. `portfolio/manager.py` `close_position()` touches all four in sequence without an explicit transaction wrapper. `CONCERNS.md`: "Position status transitions — Status field is string enum (open/closed/monitored); no FSM validation. Can set invalid transitions."

**Warning signs:**
- `portfolio/manager.py` `close_position()` or `add_position()` has more than 2 `await conn.execute()` calls without an enclosing `async with conn` transaction.
- `export/portfolio_report.py` has a 4+ table JOIN for position summary data.
- Test for position closure passes but monitoring alerts for the same ticker show stale data.
- Re-opening a position same day produces inconsistent state in `positions_thesis`.

**Prevention strategy:**
1. **Phase 1 (immediate):** Wrap all multi-step position lifecycle writes in `async with conn` transaction blocks. Prevents partial-write corruption without a schema change.
2. **Phase 2 (schema consolidation):** Introduce a `position_events` table (event log pattern): each lifecycle event (opened, analyzed, thesis_updated, alerted, closed) is an immutable row. `active_positions` becomes a materialized view computed from events. This makes audit history free (events are already logged) and eliminates complex joins.
3. **Add FSM guard:** Replace `status: str` in `portfolio/models.py` with a `PositionStatus(Enum)` class and a `valid_transitions: dict[PositionStatus, set[PositionStatus]]` map. Raise `ValueError` on invalid transitions in `close_position()`, `reopen_position()`.

**Phase to address:** Phase 1 (transaction wrappers — safety net). Phase 2 (event log — schema work).

---

### Pitfall 6: No Observability — Blind to Production Failures

**Priority:** HIGH

**What goes wrong:**
Without structured logs, traces, or metrics, production failures in the daemon or API are diagnosed only by reading raw log files. When a scheduled job silently fails (exception caught and logged but not surfaced), or when an agent consistently returns HOLD due to a data provider issue, there is no dashboard or alert to detect it. The user only discovers the problem when they notice stale analysis on the frontend.

**Competitor comparison:**
- **freqtrade** has a community-maintained [Prometheus exporter (`ftmetric`)](https://blog.kamontat.net/posts/setup-freqtrade-with-grafana) that calls FreqTrade's REST API and exposes metrics for Grafana dashboards. Docker Compose example in docs.
- **nautilus_trader** includes configurable logging with crash logs as audit trails; structured log levels by component.
- **OpenBB** defers observability entirely — no metrics, no tracing.
- **ai-hedge-fund** and **TradingAgents** have no observability beyond `print()` and debug flags.
- Industry standard (2025): `opentelemetry-instrumentation-fastapi` provides zero-code auto-instrumentation for traces and metrics. Overhead: 0.5-2ms latency per request, 2-5% CPU. GA-stable as of 2024.

**Our current state:**
`api/app.py` — Python `logging` module with named loggers, file + console handlers. No structured log format (no JSON). No metrics endpoint. No distributed traces. No dashboards. `CONCERNS.md`: "Security — Add audit logging when API keys are accessed." Daemon has rotating file handler in `logs/investment_daemon.log` (5MB max) but no alerting on error rate.

**Warning signs:**
- Support question: "Why did the agent return HOLD for AAPL yesterday?" — requires manually grepping log files.
- Daemon job "completed" in logs but signal rows missing from DB.
- Frontend shows stale analysis with no indication to user that daemon failed.
- Error rate in API not visible without tailing logs.

**Prevention strategy:**
1. **Phase 1 (structured logs):** Switch to `structlog` or Python `logging` with JSON formatter. Every log record should include: `timestamp`, `level`, `logger`, `job_name` (for daemon), `ticker` (when applicable), `duration_ms`, `error` (if any). This enables `grep`/`jq` queries on log files without a backend.
2. **Phase 1 (health endpoint):** Add `GET /health` endpoint that returns daemon last-run timestamps, job success counts, and error counts from the `job_run_log` table (from Pitfall 2 fix). Frontend dashboard can poll this.
3. **Phase 2 (OpenTelemetry):** Add `opentelemetry-instrumentation-fastapi` + `opentelemetry-instrumentation-aiosqlite`. Emit traces to local Jaeger (Docker) or directly to a free OTLP endpoint (Uptrace free tier, HyperDX). This gives request traces for latency debugging without operational overhead.
4. **Phase 2 (metrics):** Add a Prometheus metrics endpoint via `prometheus-fastapi-instrumentator`. Expose: `analysis_duration_seconds`, `agent_signal_distribution`, `yfinance_429_count`, `daemon_job_last_run`.

**Phase to address:** Phase 1 (structured logs + health endpoint). Phase 2 (OpenTelemetry + metrics).

---

### Pitfall 7: APScheduler 3.x → 4.x Migration Is a Breaking Rewrite

**Priority:** MEDIUM (future risk, not immediate)

**What goes wrong:**
APScheduler 4.x is a near-complete rewrite of 3.x. `add_job()` becomes `add_schedule()`; `AsyncIOScheduler` becomes `AsyncScheduler` (AnyIO-based); job stores are incompatible with 3.x (no automatic import of 3.x persistent job data); the `configure()` method is removed; pytz zones replaced with `zoneinfo`. Our `pyproject.toml` pins `apscheduler>=3.10,<4.0` — a correct protective constraint. However, this means we are blocked from APScheduler 4.x features (improved async, fault-tolerant data stores) until we budget for the migration.

Source: [APScheduler 4.0 progress tracking issue #465](https://github.com/agronholm/apscheduler/issues/465), [migration guide](https://apscheduler.readthedocs.io/en/master/migration.html).

**Our current state:**
`pyproject.toml` — `apscheduler>=3.10,<4.0` (correct pin). `daemon/scheduler.py` uses `AsyncIOScheduler` with cron triggers. Migration to 4.x requires: rename `AsyncIOScheduler` → `AsyncScheduler`; replace `scheduler.add_job()` → `scheduler.add_schedule()`; replace `pytz` timezone args with `zoneinfo` strings; rebuild any persistent job store.

**Warning signs:**
- `apscheduler` dependency check shows 4.x available; `pip install` without pin would upgrade silently.
- CI installs latest compatible — if `<4.0` pin is removed accidentally, next deploy breaks daemon.

**Prevention strategy:**
Maintain the `<4.0` pin indefinitely until a dedicated migration sprint is planned. When APScheduler 4.x reaches stable release, the migration should be a standalone phase deliverable with full daemon test coverage before merge. Alternative: evaluate **Celery Beat** or **Prefect** if the migration cost of APScheduler 4.x is high and a richer task queue is needed.

**Phase to address:** Note in backlog for Phase 3+; not urgent until 4.x reaches stable.

---

### Pitfall 8: Signal Weight Normalization Breaks When Agents Are Disabled

**Priority:** MEDIUM

**What goes wrong:**
`engine/aggregator.py` computes a weighted average of agent outputs. If an agent is disabled (e.g., `SentimentAgent` offline because `ANTHROPIC_API_KEY` is missing, or `MacroAgent` offline because `FRED_API_KEY` is absent), the remaining weights must sum to 1.0 for the aggregator to produce a meaningful signal. If renormalization is not automatic, a 5-agent subset uses 5-agent weights and the aggregated signal is systematically biased toward lower absolute values (weights sum < 1.0).

**Competitor comparison:**
- **TradingAgents (TauricResearch)** uses LangGraph's node-conditional routing — if an analyst node fails to produce output, LangGraph's state machine routes around it, and the debater/trader nodes receive only successful outputs. No manual weight renormalization needed.
- **ai-hedge-fund** similarly relies on LangGraph; missing analyst = missing input to synthesis, not a division error.

**Our current state:**
`engine/aggregator.py` lines 150-180. `CONCERNS.md`: "If an agent is missing or disabled, remaining weights must renormalize to 1.0. Manual renormalization error-prone. Test coverage: missing disabled-agent scenarios."

**Warning signs:**
- Analysis returns `confidence: 0.3` even though the 3 agents that ran all agree — aggregate is low because weights don't sum to 1.
- `ANTHROPIC_API_KEY` not set → SentimentAgent returns HOLD → aggregator computes weighted average of 5 agents at 80% of full weight.
- Warnings list in `AggregatedSignal` shows "SentimentAgent unavailable" but confidence is not adjusted.

**Prevention strategy:**
1. `SignalAggregator.__init__()` should accept `active_agent_names: list[str]` and auto-renormalize weights to sum to 1.0 over only active agents. Log a warning if renormalization changes any weight by >20%.
2. Add test parametrize for each single-agent-disabled scenario verifying: (a) sum of weights used == 1.0, (b) confidence is appropriately scaled.
3. Surface the effective weight set in `AggregatedSignal.metadata` so the frontend can show "ran with 3/5 agents, weights adjusted."

**Phase to address:** Phase 1 (correctness fix — low effort, high accuracy impact).

---

### Pitfall 9: Survivorship Bias in Multi-Ticker Backtests

**Priority:** MEDIUM

**What goes wrong:**
`yfinance` only returns data for tickers that currently exist. If a backtest covers 2018-2023 and includes SPY component stocks, any stock that was delisted (bankruptcy, acquisition, index removal) between 2018 and 2026 will simply return an empty DataFrame — the backtest silently excludes it. This inflates strategy returns by 1-4% annualized according to academic literature, and dramatically inflates Sharpe ratios (removing worst outcomes from the return distribution).

**Competitor comparison:**
- **zipline-reloaded** requires data bundles that include delisted securities via Quandl/Sharadar historical data.
- **QuantConnect** (cloud) provides survivorship-bias-free data as a core platform feature.
- **Norgate Data** (paid) is the standard OSS recommendation for survivorship-bias-free data.
- Free alternatives: none fully solve this; yfinance is fundamentally limited to currently listed securities.

**Our current state:**
`backtesting/engine.py` — uses data providers for all tickers. `data_providers/yfinance_provider.py` returns empty DataFrame for delisted tickers (which the pipeline treats as "no data available" — analysis skipped). No warning surfaced that a ticker was excluded due to delisting rather than missing data.

**Warning signs:**
- Backtest on S&P 500 component tickers from pre-2020 includes only survivors.
- Empty DataFrame from yfinance for a ticker triggers a warning but not a backtesting bias flag.
- Strategy shows unusually consistent positive returns across all years — missing the 2020 COVID crash delisted cohort.

**Prevention strategy:**
1. **Immediate:** When a backtest ticker returns empty data, log a specific `SURVIVORSHIP_BIAS_RISK` warning (not just "no data") with the ticker and date range. Aggregate count at end of backtest run and include in `BacktestResult` metadata.
2. **Medium term:** Allow user to supply a historical constituent list (CSV) for index-based backtests. The engine reads tickers from the historical list rather than today's index composition.
3. Document explicitly in the UI: "Backtests using yfinance may exclude delisted securities. Results may be optimistic."

**Phase to address:** Phase 1 (warning flag is trivial). Phase 2 (constituent list support).

---

### Pitfall 10: pandas_ta FutureWarnings → Eventual Pandas 4.x Breakage

**Priority:** MEDIUM

**What goes wrong:**
`pandas_ta` 0.4.25b0 (beta, our pinned version) generates `FutureWarning` on Pandas 3.x related to index handling and deprecated accessor patterns. These warnings indicate that the patterns will raise errors on Pandas 4.x. The library has not had a stable release since 2022 and the upstream author is semi-inactive.

**Competitor comparison:**
- Most OSS trading bots that use technical analysis have migrated to **TA-Lib** (C bindings via `ta-lib` Python wrapper) or **pandas-ta-classic** (community-maintained fork of pandas-ta).
- **lumibot** uses TA-Lib C bindings for core indicators.
- **freqtrade** supports both TA-Lib and pandas-ta through its strategy API, letting users choose.

**Our current state:**
`agents/technical.py` imports `pandas_ta`. `CONCERNS.md`: "pandas_ta emits Pandas 3.x FutureWarnings — waiting on upstream. May break on Pandas 4.x."

**Warning signs:**
- `FutureWarning: DataFrame.groupby with axis=1 is deprecated` in agent logs.
- Pandas upgrade in `pyproject.toml` from 2.x → 3.x would have surfaced these (if not already on 3.x).
- `pandas_ta` PyPI last release is 2022 — any Pandas minor version bump can introduce new warnings.

**Prevention strategy:**
1. **Immediate:** Pin `pandas<3.0` if currently on 2.x to prevent surprise breakage on next `pip install --upgrade`. Add a comment explaining the pin.
2. **Phase 2:** Evaluate `pandas-ta-classic` (community fork, active 2024-2025, 200+ indicators) as drop-in replacement. API is backward-compatible with original `pandas-ta`.
3. **Fallback:** If pandas-ta-classic does not cover all needed indicators, implement missing ones directly using `pandas` + `numpy` (RSI, MACD, Bollinger Bands are short implementations).

**Phase to address:** Phase 1 (pin Pandas); Phase 2 (migrate to pandas-ta-classic or ta-lib).

---

### Pitfall 11: No Docker / Self-Host Story — Setup Friction for New Environments

**Priority:** MEDIUM

**What goes wrong:**
The project has no `Dockerfile` or `docker-compose.yml`. Setup requires: Python 3.11+, Node.js, `pip install -e ".[dev]"`, `npm install`, `cp .env.example .env`, populate API keys, `python -m db.database`, then start both API and daemon. On a fresh Windows machine, this is a 30-60 minute process prone to Python version mismatches and PATH issues. No containerized option means reproducing production state locally (for debugging) requires manual environment matching.

**Competitor comparison:**
- **freqtrade** provides an official Docker image on DockerHub (`freqtradeorg/freqtrade:stable`) and a `docker-compose.yml` in the repo. Quickstart is `docker compose up -d`. Their documentation is Docker-first.
- **jesse** distributes via Docker; `docker-compose.yml` is the primary install path.
- **TradingAgents** includes a `docker` directory and Docker Compose for optional Ollama (local LLM) integration.
- **Hummingbot** runs exclusively in Docker; no native install supported for production.
- **ai-hedge-fund** includes `.dockerignore` and a `docker/` directory.

**Our current state:**
`Makefile` and `run.ps1` provide developer convenience. No `Dockerfile`. No `docker-compose.yml`. `STACK.md`: "Production — Python 3.11+ runtime, SQLite database file system access." Deploy story is "run it yourself."

**Warning signs:**
- New contributor or test environment setup takes >30 minutes.
- "Works on my machine" bugs from Python version or dependency drift.
- No way to snapshot a known-good environment for regression testing.

**Prevention strategy:**
1. **Phase 2:** Add a `Dockerfile` for the API/daemon process: `python:3.11-slim`, install dependencies, copy source, expose port 8000. Add a `docker-compose.yml` with: `api` service (FastAPI), `daemon` service (APScheduler), shared volume for `data/` directory (SQLite file).
2. The frontend can be served as a static build mounted in the same compose file via an nginx container, or served by the FastAPI app itself (`app.mount("/", StaticFiles(directory="frontend/dist"))`).
3. Add `docker compose up` to README as the primary quick-start path.

**Phase to address:** Phase 2 (deploy hardening).

---

### Pitfall 12: Static RSI/VIX Thresholds — Signal Quality Degrades in Volatility Regime Changes

**Priority:** MEDIUM

**What goes wrong:**
RSI thresholds (30/70) and VIX SMA window (20 days) are hardcoded. In high-volatility regimes (VIX > 30), RSI < 30 is common and loses discriminative power — stocks stay oversold for weeks. In low-volatility regimes (VIX < 15), RSI rarely reaches 30/70 extremes, so signals are generated less frequently. The current fix in `agents/technical.py` (context-aware RSI based on trend direction) is correct but the base thresholds still don't adapt to regime volatility level.

**Competitor comparison:**
- **vectorbt** handles this at the simulation level — users parameterize thresholds and vectorbt runs thousands of parameter combinations to find regime-appropriate values via optimization.
- **freqtrade**'s `hyperopt` command runs Bayesian optimization over strategy parameters including indicator thresholds, producing regime-specific optimal values.
- **nautilus_trader** supports adaptive parameters via `Parameter` objects that can be updated at runtime from market feedback.

**Our current state:**
`agents/technical.py` — RSI thresholds 30/70 hardcoded post-aaeb90b fix. `agents/macro.py` — VIX SMA window hardcoded to 20 days. `CONCERNS.md`: "RSI thresholds (30/70) hardcoded; may need adjustment for different volatility regimes. SMA window (20 days) not validated against market turbulence cycles."

**Warning signs:**
- TechnicalAgent returns HOLD for extended periods during known high-volatility periods (2020 COVID, 2022 rate hikes).
- TechnicalAgent BUY signals cluster in low-VIX periods and are sparse in high-VIX periods — non-uniform signal distribution across time.

**Prevention strategy:**
1. **Phase 2:** Expose RSI thresholds and VIX SMA window as configurable parameters in `DaemonConfig` or a per-agent config file. Allow per-asset-class overrides (crypto vs. equity vs. macro).
2. **Phase 2:** Add a `volatility_regime` field from `MacroAgent` output — `high_vol` / `normal_vol` / `low_vol` — and let `TechnicalAgent` widen/narrow RSI band based on this. (e.g., high-vol regime: RSI thresholds 20/80; low-vol regime: 35/65).
3. Validate with backtest comparison: run same strategy with static vs. adaptive thresholds over 2018-2025, covering multiple volatility regimes.

**Phase to address:** Phase 2 (after observability is in place — need metrics to validate improvement).

---

### Pitfall 13: Multi-Process Daemon + API Without Authentication

**Priority:** MEDIUM (security surface)

**What goes wrong:**
The API has no authentication layer. On a developer's local machine with a trusted network, this is acceptable. However, if the FastAPI server binds to `0.0.0.0` (default in many configurations), the full portfolio and thesis data is accessible to any device on the local network. More acutely: the daemon uses a shared SQLite file — if a second instance of the API or daemon is accidentally started, two writers compete for the SQLite lock with no coordination.

**Competitor comparison:**
- **freqtrade** requires an API key for the REST API (`api_server.listen_ip_address`, `api_server.jwt_secret_key` in config.json). No unauthenticated access.
- **OpenBB** in enterprise mode has SSO and RBAC.
- **nautilus_trader** is process-local with no external API surface by default.

**Our current state:**
`api/app.py` — no auth middleware. `CONCERNS.md`: "No authentication on REST API — system designed for self-hosted use; no auth layer means local network access = full portfolio exposure." `api/deps.py` has a `get_db_path` dependency but no auth dependency.

**Warning signs:**
- API server starts with `--host 0.0.0.0` (or if bound to LAN interface by default).
- No `Authorization` header required for portfolio endpoints.
- Two instances of the daemon process detected in `ps aux` (restart without stop).

**Prevention strategy:**
1. **Phase 1 (quick):** Ensure default `uvicorn` bind is `127.0.0.1` (localhost), not `0.0.0.0`. Document this explicitly in startup scripts and `run.ps1`.
2. **Phase 2 (optional API key):** Add a simple API key middleware: `X-API-Key` header required, checked against `API_KEY` environment variable. Unauthenticated requests return 401. This is the freqtrade model — lightweight, no user DB needed.
3. **Daemon deduplication:** Add a PID file (`data/daemon.pid`). On startup, check if PID file exists and process is running; abort if so. Clean up PID file on graceful shutdown.

**Phase to address:** Phase 1 (localhost binding + PID file). Phase 2 (API key middleware).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Global yfinance lock instead of per-ticker lock | Prevents data corruption immediately | Serializes all downloads; blocks concurrent agent execution | Acceptable only while portfolio < 50 tickers and no concurrent backtests |
| SQLite instead of Postgres | Zero setup, file-based backup, works offline | Single-writer bottleneck, no horizontal scale | Acceptable while single-user and < 200 positions |
| APScheduler 3.x in-process with FastAPI | Simple deployment, one process | Multi-worker duplication risk, no crash recovery, job state in-memory only | Acceptable while single-process deployment |
| String enum for position status | Simple to add states | No FSM validation; invalid transitions silently accepted | Never acceptable for production — replace with Enum + transition guard |
| `try/except Exception: log()` in daemon jobs | Prevents crash | Swallows partial write failures, makes debugging impossible | Never acceptable for DB operations; acceptable only for network errors |
| Static sector P/E medians table | No external call needed | Stale during sector rotation events; incorrect during crashes | Acceptable as long as it's updated quarterly and flagged in UI |
| No Dockerfile | Fewer moving parts during development | 30+ minute setup time for new environments | Acceptable during solo development; not acceptable for any sharing or deployment |
| pandas_ta (unmaintained) | 130+ indicators available | May break on Pandas 4.x; FutureWarnings in logs now | Acceptable only until pandas-ta-classic migration is prioritized |
| Signal history table (unbounded growth) | No maintenance required | Analytics queries slow after ~50k rows; disk growth | Never acceptable — add retention/archive policy before 90 days of data |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| yfinance batch download | Calling `yf.Ticker(t).history()` per ticker in a loop | Use `yfinance.download([t1, t2, t3], group_by='ticker')` — one HTTP call for N tickers |
| yfinance concurrent calls | Using `asyncio.gather()` with separate `download()` calls | All yfinance calls must go through a single semaphore or process queue; `asyncio.gather()` with `run_in_executor` still hits the `_DFS` race condition |
| APScheduler in FastAPI | Starting `AsyncIOScheduler` inside a FastAPI lifespan event with multiple Uvicorn workers | Run APScheduler in a dedicated process (`python -m daemon.scheduler`) separate from the API server |
| SQLite + aiosqlite | Opening a new connection per coroutine | Use connection pool (`db/connection_pool.py` already exists); ensure WAL mode is set on first connection |
| Anthropic Claude API | Calling sentiment agent synchronously in pipeline | Already async; but need circuit breaker — if API returns 429, skip sentiment (not block pipeline) |
| CCXT crypto exchange | Using REST polling for price updates | CCXT supports WebSocket streams for live price; REST polling at 1s intervals for 20+ symbols hits rate limits |
| FRED API | Fetching macro indicators on every analysis request | FRED data is daily/monthly — cache with 24h TTL; fetching on every request is wasteful and risks 429 |
| pandas_ta | Upgrading Pandas without testing | Run `pytest tests/test_005_technical_agent.py -W error::FutureWarning` after any Pandas upgrade to catch breakage before production |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| yfinance serial downloads during backtest | Backtest for 100 tickers takes 50+ seconds before first result | Pre-download data to Parquet; use multi-ticker batch syntax | At ~25 tickers (noticeable lag) |
| Signal history table full scan | Portfolio analytics page loads in >3s | Add composite index `(portfolio_id, timestamp)`; add 90-day retention | At ~50,000 signal rows (~18 months of daily operation on 20-ticker portfolio) |
| Monte Carlo 10,000 iterations in Python loop | Risk page hangs for 5+ seconds | Vectorize with numpy; or cap iterations at 1,000 for UI and run full simulation as background job | At any portfolio size — this is slow on first load |
| asyncio.gather() with yfinance in executor | Apparent parallelism but actual serialization via lock | Use true parallelism via subprocess pool OR pre-download pattern | At >5 concurrent agent runs |
| In-memory LRU cache (no disk persistence) | Cache warm on startup takes N×download time on every restart | Add disk-backed cache (Parquet or SQLite) that survives restart | Every restart of the daemon |
| No indexes on backtest result tables | Backtest history page slow to filter/sort | Add index on `(ticker, started_at)` in backtesting results table | After 100+ stored backtest runs |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| API binding to `0.0.0.0` | Full portfolio exposure to LAN; sensitive thesis data readable | Default bind to `127.0.0.1`; make LAN binding opt-in with explicit config |
| Credentials in error messages | SMTP user/host, Telegram token partially leaked in exception strings | Sanitize all exception messages before logging; use structured logging with separate `credentials_scrubbed: true` field |
| No API key rotation mechanism | Compromised ANTHROPIC_API_KEY or TELEGRAM_BOT_TOKEN remains valid indefinitely | Document rotation procedure in CONTRIBUTING.md; add `GET /health/secrets-age` endpoint that shows days since last rotation (self-reported via env var) |
| Long-lived API keys in `.env` file | Single `.env` file is single point of failure | For non-local deployments, use OS keyring (`keyring` library) or environment injection via Docker secrets |
| No rate limiting on `/analyze` endpoint | Burst of frontend requests can exhaust yfinance rate limit or Anthropic quota | Add `slowapi` middleware for per-IP rate limiting on analysis and backtest endpoints |
| SMTP over unencrypted channel | Credentials and alert content visible in transit | Force `SMTP_USE_TLS=true`; fail loudly if TLS negotiation fails rather than falling back |

---

## "Looks Done But Isn't" Checklist

- [ ] **yfinance rate limiting:** The rate limiter in `data_providers/rate_limiter.py` limits calls — but does it also handle Yahoo 429 responses (retry with backoff)? Verify `yfinance_provider.py` has retry logic on HTTP 429, not just a pre-call rate limiter.
- [ ] **Agent weight normalization:** `engine/aggregator.py` appears to aggregate signals — but verify it auto-renormalizes when agents are skipped, not just when explicitly disabled.
- [ ] **Backtest point-in-time:** `backtesting/data_slicer.py` slices price history — but `FundamentalAgent` is called inside the backtest loop with current yfinance financials. Verify there is a `backtest_mode` flag that disables or stubs fundamental analysis.
- [ ] **Position closure atomicity:** `portfolio/manager.py` `close_position()` appears to work — but verify all writes (active_positions update, trade_records insert, signal_history FK update) happen in a single database transaction, not sequential `await conn.execute()` calls.
- [ ] **Daemon deduplication:** `daemon/scheduler.py` starts on `python -m daemon.scheduler` — but verify there is a PID file or process guard preventing two daemon instances from running simultaneously.
- [ ] **Signal history retention:** `tracking/store.py` writes signals — but verify a retention/archive job exists. Without pruning, the table grows without bound.
- [ ] **Sector P/E freshness:** `agents/fundamental.py` uses `SECTOR_PE_MEDIANS` — but verify these values are documented with a last-updated date and there is a process (manual or automated) to refresh them quarterly.
- [ ] **Alert delivery reliability:** `notifications/email_dispatcher.py` sends alerts — but verify the daemon logs whether the email was accepted by the SMTP relay, not just whether `sendmail()` returned without exception.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| yfinance lock serialization causes backtest timeout | MEDIUM | Add local Parquet cache; re-run backtest using cached data. Short-term: reduce ticker count per batch. |
| APScheduler job partial DB write on crash | MEDIUM | Query `job_run_log` for `status='running'` rows; identify affected date range; manually re-run daemon job via `daemon_cli.py run-job daily_check`. Verify signal completeness. |
| SQLite database locked error | LOW | Set `PRAGMA journal_mode=WAL` via admin script if not already set. Add index. Restart processes to release connections. For acute lock: `sqlite3 data/investment_agent.db '.tables'` to detect open connections. |
| Look-ahead bias in existing backtest results | HIGH | Historical backtest results must be invalidated. Add `backtest_mode` flag; re-run all backtests with fundamental agent stubbed. Document new vs old results. |
| Position lifecycle inconsistency after crash | HIGH | Run data integrity check script: count active_positions vs trade_records vs signal_history for each portfolio. Identify orphaned records. Manual SQL repair or rollback from last consistent backup. |
| APScheduler 3.x → 4.x accidental upgrade | HIGH | Pin `apscheduler<4.0` in `pyproject.toml`. If accidentally upgraded: `pip install apscheduler==3.10.x`. Job schedule definitions require rewriting for 4.x API. |
| pandas_ta breaks on Pandas upgrade | MEDIUM | Pin `pandas<X.0` immediately. Migrate affected indicator calculations to `pandas-ta-classic` or manual implementation. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Priority | Prevention Phase | Verification |
|---------|----------|------------------|--------------|
| yfinance global lock / Parquet cache | HIGH | Phase 1 | Backtest 100 tickers completes in <20s; no `_yfinance_lock` contention in profiles |
| APScheduler crash recovery / job log | HIGH | Phase 1 | `job_run_log` table exists; crash simulation test passes; no orphaned signals after forced kill |
| SQLite indexes + pruning | HIGH | Phase 1 | Analytics page loads <1s on 50k signal row DB; no `database is locked` errors in 24h soak test |
| Look-ahead bias flag in backtest | HIGH | Phase 1 | `backtest_mode=True` → FundamentalAgent returns HOLD with warning; test verifies |
| Position lifecycle transactions | HIGH | Phase 1 | All multi-step position writes wrapped in transactions; concurrent close+reopen test passes |
| Observability (structured logs + health endpoint) | HIGH | Phase 1 | `GET /health` returns daemon timestamps; logs are JSON-parseable |
| Agent weight normalization on missing agent | MEDIUM | Phase 1 | Test: disable SentimentAgent → remaining weights sum to 1.0 → confidence not deflated |
| Survivorship bias warning | MEDIUM | Phase 1 | Empty yfinance DataFrame for backtest ticker logs `SURVIVORSHIP_BIAS_RISK` |
| pandas_ta migration to pandas-ta-classic | MEDIUM | Phase 2 | Zero `FutureWarning` in test suite after migration |
| Adaptive RSI/VIX thresholds | MEDIUM | Phase 2 | Backtest comparison shows improved signal distribution across volatility regimes |
| Docker / self-host story | MEDIUM | Phase 2 | `docker compose up` starts API + daemon on fresh machine in <5 min |
| API authentication (API key middleware) | MEDIUM | Phase 2 | `curl http://localhost:8000/portfolio/positions` returns 401 without API key |
| OpenTelemetry + Prometheus metrics | MEDIUM | Phase 2 | Traces visible in local Jaeger; `GET /metrics` returns prometheus exposition format |
| APScheduler 4.x migration | LOW | Phase 3+ | Tracked in backlog; not until 4.x reaches stable |
| SQLite → Postgres migration | LOW | Phase 3+ | Schema-neutral queries pass against both backends |

---

## Sources

- yfinance thread safety race condition: [GitHub issue #2557](https://github.com/ranaroussi/yfinance/issues/2557) (opened June 2025, open)
- yfinance rate limiting (429): [GitHub issue #2128](https://github.com/ranaroussi/yfinance/issues/2128), [issue #2422](https://github.com/ranaroussi/yfinance/issues/2422), [issue #2125](https://github.com/ranaroussi/yfinance/issues/2125)
- freqtrade SQLite CPU performance with FreqUI: [GitHub issue #6791](https://github.com/freqtrade/freqtrade/issues/6791)
- APScheduler 3→4 migration: [official migration guide](https://apscheduler.readthedocs.io/en/master/migration.html), [4.0 progress tracking issue #465](https://github.com/agronholm/apscheduler/issues/465)
- APScheduler common mistakes: [Sepehr Ghorbanpoor, Medium](https://sepgh.medium.com/common-mistakes-with-using-apscheduler-in-your-python-and-django-applications-100b289b812c)
- APScheduler SQLAlchemyJobStore OperationalError: [GitHub issue #499](https://github.com/agronholm/apscheduler/issues/499)
- freqtrade lookahead analysis tool: [official docs](https://www.freqtrade.io/en/stable/lookahead-analysis/)
- freqtrade persistence migrations (FSM model): [freqtrade/persistence/migrations.py](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/persistence/migrations.py)
- nautilus_trader architecture (single-threaded kernel, actor model, crash-only): [official concepts docs](https://nautilustrader.io/docs/latest/concepts/architecture/)
- Hummingbot Clock-driven architecture: [Hummingbot blog part 1](https://hummingbot.org/blog/hummingbot-architecture---part-1/)
- OpenBB FastAPI provider architecture: [OpenBB platform docs](https://docs.openbb.co/platform/), [architecture blog](https://openbb.co/blog/exploring-the-architecture-behind-the-openbb-platform)
- TradingAgents (TauricResearch) LangGraph multi-agent: [GitHub](https://github.com/TauricResearch/TradingAgents)
- ai-hedge-fund (virattt) architecture: [GitHub](https://github.com/virattt/ai-hedge-fund)
- zipline-reloaded point-in-time data and event-driven backtesting: [GitHub](https://github.com/stefan-jansen/zipline-reloaded)
- Survivorship bias in backtesting with yfinance: [adventuresofgreg.blog 2026](http://adventuresofgreg.com/blog/2026/01/14/survivorship-bias-backtesting-avoiding-traps/), [quantrocket.com](https://www.quantrocket.com/blog/survivorship-bias/)
- Look-ahead bias — point-in-time fundamental data: [INRIA hal-05466549 (2025)](https://inria.hal.science/hal-05466549v1/file/lookahead.pdf)
- OpenTelemetry Python FastAPI auto-instrumentation: [opentelemetry-python-contrib docs](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html), [Last9 guide](https://last9.io/blog/integrating-opentelemetry-with-fastapi/)
- freqtrade Prometheus/Grafana integration community: [KCBlog](https://blog.kamontat.net/posts/setup-freqtrade-with-grafana)
- SQLite WAL single-writer bottleneck: [SQLite WAL docs](https://www.sqlite.org/wal.html), [oldmoe blog 2024](https://oldmoe.blog/2024/07/08/the-write-stuff-concurrent-write-transactions-in-sqlite/)
- pandas-ta-classic community fork: [GitHub xgboosted/pandas-ta-classic](https://github.com/xgboosted/pandas-ta-classic), [PyPI](https://pypi.org/project/pandas-ta-classic/)
- Our project codebase: `.planning/codebase/CONCERNS.md`, `data_providers/yfinance_provider.py`, `daemon/scheduler.py`, `engine/aggregator.py`, `db/database.py`, `portfolio/manager.py`

---
*Pitfalls research for: OSS investment-agent / trading-bot ecosystem (Architecture & Deploy Story dimension)*
*Researched: 2026-04-21*
