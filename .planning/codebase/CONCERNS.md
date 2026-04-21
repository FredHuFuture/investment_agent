# Codebase Concerns

**Analysis Date:** 2026-04-21

## Tech Debt

**Expected/Actual data fragmented across 3 tables:**
- Issue: Position lifecycle data split between `active_positions` (open/closed status), `trade_records` (historical P&L), and `signal_history` (agent outputs). Queries to correlate thesis expectations with realized outcomes require complex multi-table joins.
- Files: `db/database.py` (schema), `portfolio/manager.py` (position management), `export/portfolio_report.py` (query aggregation)
- Impact: Difficult to maintain consistency, slow analytics queries, high risk of data misalignment during position closure/reopening cycles
- Fix approach: Consolidate into unified `trade_records` table with all lifecycle fields (thesis info, entry/exit, signals, outcomes). Requires migration of ~6 API endpoints and 15+ test fixtures.

**Pandas 3.x deprecation warnings from pandas_ta:**
- Issue: The `pandas_ta` library generates `FutureWarning` on Pandas 3.x compatibility. Filtering in tests but still present in production logs.
- Files: `agents/technical.py` (imports `pandas_ta` for indicators)
- Impact: Console noise, potential breakage if pandas_ta isn't updated before Pandas 4.x. Currently set to "wait for upstream fix" in ROADMAP.md.
- Fix approach: Monitor upstream `pandas_ta` releases; when fixed, remove warning filters. Current workaround in place but blocks clean test output.

**yfinance thread-safety serialization:**
- Issue: yfinance is not thread-safe due to corrupted internal MultiIndex column handling on concurrent calls. All downloads serialized via `_yfinance_lock` (threading.Lock), creating a bottleneck.
- Files: `data_providers/yfinance_provider.py` (lines 15-16, 33-40, 73)
- Impact: Rate-limited to 2 calls/second globally; backtesting with many tickers (100+) becomes very slow. Lock held across full download+parse cycle.
- Fix approach: Migrate to batch-safe data provider (e.g., yfinance_nospam, cached batch requests) or async subprocess pool to avoid shared lock. Low priority unless backtesting latency becomes critical.

---

## Critical Model Accuracy Fixes (Commit aaeb90b)

**Recent fix (2026-03-19): 15 issues across 9 files:**
- All 517 tests pass post-fix, but several agents had context-insensitive scoring:

**TechnicalAgent context-blind RSI:**
- Issue: RSI scoring did not account for trend direction. Oversold conditions (RSI < 30) scored identically in uptrends vs downtrends.
- Files: `agents/technical.py`
- Fix: Context-aware RSI scoring (uptrend: +10, downtrend: -5), 5-bar momentum for trend detection, re-clamp trend_score after weekly.
- Residual risk: RSI thresholds (30/70) hardcoded; may need adjustment for different volatility regimes.

**FundamentalAgent missing sector-relative P/E:**
- Issue: P/E scoring used absolute thresholds (e.g., P/E < 15 is good) without considering sector median. Tech stocks naturally have higher P/E.
- Files: `agents/fundamental.py`
- Fix: Added 12-sector median P/E table (SECTOR_PE_MEDIANS), relative scoring now compares to sector median.
- Residual risk: Sector PE medians are static (updated periodically). During sector rotation events, thresholds may lag market reality.

**FundamentalAgent missing-data penalty weak:**
- Issue: Confidence not sufficiently penalized when 4+ of 8 key metrics missing (missing fundamentals indicate data quality issues).
- Files: `agents/fundamental.py`
- Fix: Added -25% confidence penalty for missing data counts >= 4.
- Residual risk: Penalty is static; may be too aggressive for thinly-traded stocks or too lenient for large caps.

**MacroAgent static VIX thresholds:**
- Issue: VIX signal used absolute thresholds (VIX > 25 = bearish) without normalizing to market conditions. High VIX during crisis != high VIX during complacency.
- Files: `agents/macro.py`
- Fix: Changed to relative VIX (ratio to 20-day SMA) as primary signal; asset-type differentiated regime mapping.
- Residual risk: SMA window (20 days) not validated against market turbulence cycles. May need dynamic adjustment.

**CryptoAgent network adoption bias:**
- Issue: Network adoption weighted 10% (highest), acting as static constant bias toward bullish signals. Outdated for mature assets.
- Files: `agents/crypto.py`
- Fix: Reduced to 5%, redistributed weight to momentum (+2.5%) and volatility (+2.5%).
- Residual risk: Weight distribution still uniform across BTC/ETH. Crypto market structure differs; BTC adoption cycles != ETH DeFi cycles.

**CryptoAgent price source priority unclear:**
- Issue: Fallback logic between yfinance and key_stats (for ATH) was ad-hoc.
- Files: `agents/crypto.py`
- Fix: Provider-first DI with yfinance fallback; ATH now sourced from key_stats when available.
- Residual risk: key_stats ATH may lag actual on-chain ATH by weeks. No on-chain data integration yet.

**MonteCarloSimulator i.i.d. assumption violated:**
- Issue: Used random resampling for volatility scenarios, but market volatility clusters (high-vol days follow high-vol days). Independence assumption breaks down.
- Files: `engine/monte_carlo.py`
- Fix: Block bootstrap (block_size=5) preserves volatility clustering.
- Residual risk: Block size (5 days) is hard-coded. Optimal block size varies by asset class; equities may need 10, crypto 3.

**WeightAdapter single-direction optimization:**
- Issue: Threshold grid search optimized BUY threshold only; SELL thresholds not independently optimized. Asymmetric entry/exit quality.
- Files: `engine/weight_adapter.py`
- Fix: Independent grid search for BUY and SELL thresholds.
- Residual risk: Search space is O(n^2); may be slow with fine-grained grids. No timeout or early stopping.

---

## Known Bugs & Edge Cases

**SHORT position drift sign inversion (FIXED in Sprint 13):**
- Was: SHORT positions showed wrong drift direction in monitoring alerts
- Fixed in: `monitoring/checker.py` drift calculation
- Status: Verified by tests `test_013_*.py`

**Stock split thesis invalidation (FIXED in Sprint 13):**
- Was: Target/stop loss prices broke after stock splits
- Fixed in: `portfolio/manager.py` position thesis adjustment
- Status: Migrated to use market_value instead of cost_basis for exposure %

**Portfolio exposure using cost_basis instead of market_value (FIXED in Sprint 9):**
- Status: Resolved

**Partial unique constraint on reopened tickers (FIXED in Sprint 9):**
- Was: Could not reopen position for same ticker after closing
- Fixed in: `db/database.py` migration to partial unique index
- Status: Migration handles auto-cleanup on startup

**Data inconsistency during position re-entry:**
- Issue: Closing a position and immediately re-opening same ticker can create race condition where old position ID references are stale in `positions_thesis`.
- Files: `portfolio/manager.py` (close_position, add_position), `db/database.py` (foreign keys)
- Risk: Low but possible in rapid entry/exit scenarios
- Workaround: Ensure position closure completes atomically before re-entry. Add database transaction wrapper.

---

## Security Considerations

**API key exposure in environment variables:**
- Risk: ANTHROPIC_API_KEY, FRED_API_KEY, SMTP_PASSWORD, TELEGRAM_BOT_TOKEN exposed via environment variables
- Files: `.env.example` documents expected vars; `agents/sentiment.py`, `data_providers/fred_provider.py`, `notifications/email_dispatcher.py` read from `os.getenv()`
- Current mitigation: .env files are .gitignored; keys never committed. Graceful degradation if keys missing.
- Recommendations:
  1. Add warning logs when keys are missing (already done for ANTHROPIC_API_KEY)
  2. Consider secrets manager integration (e.g., AWS Secrets Manager, HashiCorp Vault) for production
  3. Rotate TELEGRAM_BOT_TOKEN and SMTP credentials periodically
  4. Add audit logging when API keys are accessed

**SMTP credential handling:**
- Risk: SMTP_PASSWORD passed in plaintext over network (unless TLS enforced)
- Files: `notifications/email_dispatcher.py` (lines 269-274)
- Current mitigation: Uses `server.starttls()` if available; falls back to unencrypted for compatibility
- Recommendations: Force TLS for all SMTP connections; log warnings if TLS not available

**No rate limiting on public API endpoints:**
- Risk: Endpoints like `/analyze/{ticker}` can be abused to spam external data providers (yfinance, FRED, news APIs)
- Files: `api/routes/analyze.py`, `api/routes/backtest.py`, `api/routes/watchlist.py`
- Current mitigation: Rate limiter exists on data provider layer (`AsyncRateLimiter`), but no API-level throttling
- Recommendations: Add per-IP or per-token rate limiting middleware (FastAPI middleware); implement circuit breaker for cascading failures

**No authentication on REST API:**
- Risk: System designed for self-hosted use; no auth layer means local network access = full portfolio exposure
- Files: `api/app.py` (no auth middleware)
- Current mitigation: Intended for personal use; assume trusted network
- Recommendations: For production deployments, add optional JWT or API key auth layer

**Credential leakage in error messages:**
- Risk: Exception messages may contain partial credentials (e.g., "Failed to connect to user@smtp.host")
- Files: `notifications/email_dispatcher.py`, `data_providers/fred_provider.py`
- Current mitigation: Exceptions caught and sanitized in daemon/jobs.py
- Recommendations: Scrub usernames/hosts from error messages; use structured logging

---

## Performance Bottlenecks

**yfinance global rate limit bottleneck:**
- Problem: 2 calls/second globally serialized via threading.Lock. Backtesting 100 tickers = 50 seconds just for downloads.
- Files: `data_providers/yfinance_provider.py` (lines 24-27, 33-40)
- Cause: yfinance internal MultiIndex corruption on concurrent calls
- Improvement path:
  1. Batch downloads: 5 tickers per yfinance.download() call (supports multi-ticker syntax)
  2. Implement connection pool with separate locks per ticker
  3. Cache price history locally; only fetch new bars incrementally

**Large agent computations without async:**
- Problem: TechnicalAgent calculates 30+ indicators per ticker; FundamentalAgent makes 2 HTTP calls sequentially.
- Files: `agents/technical.py`, `agents/fundamental.py`
- Cause: Indicator calculations are CPU-bound; data fetches block on I/O
- Improvement path: Use `asyncio.gather()` for parallel data fetches; offload indicator calc to thread pool

**Monte Carlo simulations are slow:**
- Problem: 10,000 iterations of block bootstrap takes ~2-5 seconds per ticker
- Files: `engine/monte_carlo.py` (lines 58-100)
- Cause: Pure Python nested loops; no vectorization
- Improvement path: Use numpy for vectorized resampling; consider limiting iterations based on portfolio size

**Portfolio value history queries unindexed:**
- Problem: Analytics queries (`engine/analytics.py`) scan full `portfolio_snapshots` table to compute returns
- Files: `db/database.py` (schema), `engine/analytics.py` (queries)
- Cause: No indexes on timestamp or portfolio_id in snapshots table
- Improvement path: Add composite index on (portfolio_id, timestamp); add daily snapshot aggregation table for fast lookups

**Signal history table growth unbounded:**
- Problem: `signal_history` grows 50-100 rows/day; no pruning or archival strategy
- Files: `db/database.py`, `tracking/store.py`
- Cause: Every analysis generates 4-6 signal rows; no cleanup job
- Improvement path: Archive signals > 90 days old to separate table; add retention policy

---

## Fragile Areas

**Signal aggregator weight normalization:**
- Files: `engine/aggregator.py` (lines 150-180)
- Why fragile: If an agent is missing or disabled, remaining weights must renormalize to 1.0. Manual renormalization error-prone.
- Safe modification: Add unit test for all single-agent disable scenarios; validate sum = 1.0 in aggregator.__init__
- Test coverage: `test_008_signal_aggregator.py` covers default case but missing disabled-agent scenarios

**Data provider fallback chain:**
- Files: `agents/sentiment.py` (news fetching), `agents/crypto.py` (ATH lookup)
- Why fragile: If primary source (Brave Search, key_stats) fails, fallback (DuckDuckGo, yfinance) may return stale/different data
- Safe modification: Log when fallback triggered; add schema field to track data source per row
- Test coverage: `test_004_data_providers.py` mocks both providers; real failures not tested

**Daemon job exception handling:**
- Files: `daemon/jobs.py` (all job functions)
- Why fragile: Every job has try/except that catches all exceptions and logs. Swallows subtle bugs (e.g., partial DB transaction failure where some rows written, some not).
- Safe modification: Separate exception handling: catch expected exceptions (network errors, missing data) vs unexpected (DB locks, corruption). Re-raise critical failures.
- Test coverage: `test_030_daemon_jobs.py` mocks all external dependencies; real failure scenarios not tested

**Position status transitions:**
- Files: `portfolio/manager.py` (add_position, close_position, reopen_position)
- Why fragile: Status field is string enum (open/closed/monitored); no FSM validation. Can set invalid transitions (e.g., monitored -> open).
- Safe modification: Replace status string with Enum class; add @property validators for valid transitions
- Test coverage: Tests check happy path; edge cases (double-close, invalid transitions) not covered

**Sector/industry metadata from yfinance:**
- Files: `agents/fundamental.py`, `portfolio/manager.py`
- Why fragile: Sector names inconsistent across yfinance versions (e.g., "Financial Services" vs "Financials"). SECTOR_PE_MEDIANS uses lowercase; yfinance returns mixed case.
- Safe modification: Normalize sector names on load: `sector.lower().strip()` + mapping table for aliases
- Test coverage: `test_006_fundamental_agent.py` uses mock data; real yfinance sector mappings not tested

---

## Scaling Limits

**SQLite single-writer constraint:**
- Current capacity: ~1 position update/second sustained; bursts up to 10 without WAL
- Limit: 100+ concurrent requests saturate sqlite WAL lock
- Scaling path: Migrate to PostgreSQL with connection pooling (pgbouncer); schema-neutral migration possible via ORM

**Backtesting batch runner memory:**
- Current capacity: 50 tickers × 5 agent combos × 5 years history = 1.2GB RAM
- Limit: 200+ tickers × 10 combos exceeds 16GB on typical machine
- Scaling path: Implement streaming backtest (process 10 tickers at a time, write results to disk); incremental results aggregation

**News scraping rate limits:**
- Current capacity: Catalyst scanner makes ~5 news API calls/hour per position
- Limit: 50-position portfolio = 250 calls/day; most providers throttle at 1000/day
- Scaling path: Implement shared news cache (fetch once per ticker/day, share across positions); add news deduplication

**Daemon memory leak with long-running tasks:**
- Current capacity: Daemon runs continuously; no memory growth observed in 7-day test runs
- Limit: Unknown; potential leaks in async task cleanup (connection pool, event loop)
- Scaling path: Add periodic memory profiling; implement connection pool connection recycling every 24h

---

## Dependencies at Risk

**yfinance maintenance burden:**
- Risk: yfinance is community-maintained; MultiIndex handling changes frequently. version 0.2+ introduced breaking column format changes.
- Impact: Backtesting and technical analysis break when yfinance updates.
- Migration plan: Identify alternative (polygon.io, alpha_vantage, IEX Cloud); build provider abstraction if not already present (exists: `data_providers/base.py`). Recommend pinning yfinance version in requirements with manual update testing.

**Anthropic API key dependency for sentiment analysis:**
- Risk: Anthropic rate limits, pricing changes, service discontinuity.
- Impact: Sentiment agent returns HOLD (default) if API unavailable; portfolio analysis degrades but doesn't crash.
- Migration plan: Already has graceful degradation. Recommend fallback sentiment source (FinBERT local model, news sentiment APIs like MarketAux).

**pandas-ta deprecation:**
- Risk: Library generates FutureWarnings on Pandas 3.x; not actively maintained.
- Impact: Technical indicator calculations still work but logs noisy; may break on Pandas 4.x.
- Migration plan: Monitor upstream releases; if unmaintained, implement TA-Lib port or migrate to pandas-ta successor (ta-lib C bindings).

---

## Missing Critical Features

**On-chain metrics for crypto analysis:**
- Problem: CryptoAgent uses price-based metrics only. No access to on-chain data (MVRV ratio, SOPR, exchange flows) which are leading indicators for BTC cycles.
- Blocks: Can't confidently trade BTC/ETH relative to macro cycles; forced to rely on price momentum
- Priority: Medium (deferred to Sprint 17+)

**Validation/sanity-check agent:**
- Problem: No agent cross-checks signal quality. If TechnicalAgent is wrong, no mechanism to flag it before aggregation.
- Blocks: Can't identify systematic failures in agent logic; relies on post-facto accuracy tracking
- Priority: Low (architecture supports adding later)

**Point-in-time fundamental data:**
- Problem: FundamentalAgent uses yfinance which provides current/restated financials. Backtesting results are overfitted (used future data).
- Blocks: Backtests not reliable for out-of-sample validation
- Priority: High for backtesting confidence; cost is $20-50/month for FMP data; deferred due to cost

---

## Test Coverage Gaps

**Data provider error handling:**
- What's not tested: Network errors, timeouts, partial/malformed responses
- Files: `data_providers/yfinance_provider.py`, `data_providers/fred_provider.py`, `data_providers/news_provider.py`
- Risk: Production failures in real network conditions; mocks hide fragility
- Recommended tests: Retry logic, circuit breaker behavior, graceful degradation

**Daemon job cascading failures:**
- What's not tested: What happens when alert dispatch fails after monitoring check completes? Are alerts orphaned?
- Files: `daemon/jobs.py` (run_daily_check, run_catalyst_scan)
- Risk: Silent data loss; alerts created but not sent; trades not tracked
- Recommended tests: Simulate SMTP/Telegram failures mid-job; verify state consistency

**Position lifecycle edge cases:**
- What's not tested: Re-opening position same day; closing position twice; modifying thesis on closed position
- Files: `portfolio/manager.py`
- Risk: Database constraint violations; inconsistent state in frontend
- Recommended tests: Fuzzing position state transitions; add FSM validator

**Multi-portfolio data isolation:**
- What's not tested: Can a query from portfolio A see data from portfolio B?
- Files: `api/routes/portfolio.py`, `api/routes/watchlist.py`
- Risk: Portfolio data leakage between profiles
- Recommended tests: Create 2 portfolios, add positions to each, verify queries don't cross-contaminate

**Notification delivery reliability:**
- What's not tested: What if email is sent but marked as spam? Telegram API throttles?
- Files: `notifications/email_dispatcher.py`, `notifications/telegram_dispatcher.py`
- Risk: User misses critical alerts because they're silently filtered
- Recommended tests: Mock email provider; verify retry behavior; test HTML rendering in major clients

---

*Concerns audit: 2026-04-21*
