# Feature Coverage Analysis: Data & Integrations Dimension

**Domain:** OSS Investment Agents / Algorithmic Trading / AI-Finance
**Researched:** 2026-04-21
**Research type:** Competitive — Data Coverage & Integrations
**Overall confidence:** MEDIUM (most findings verified via official docs/READMEs; rate-limit details from multiple secondary sources)

---

## Scope

Compares the top 15+ active OSS investment-agent and trading projects across five dimensions:
1. Asset classes covered
2. Data provider integrations (free and paid)
3. Caching, rate-limit, and connection-pool strategies
4. Alternative / unconventional data
5. Fundamentals depth

For each area: what competitors cover, what **we** cover today, and categorisation as **table stakes / differentiator / anti-feature**.

---

## Projects Surveyed

| # | Project | GitHub | Stars (approx.) | Last Active | Language | Primary Focus |
|---|---------|--------|-----------------|-------------|----------|---------------|
| 1 | **OpenBB** | [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB) | 35 k+ | 2026-active | Python | Data platform / research terminal |
| 2 | **ai-hedge-fund** | [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | 9 k+ | 2025-active | Python | Multi-agent LLM fund POC |
| 3 | **TradingAgents** | [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | 5 k+ | 2026-active (v0.2.3) | Python | Multi-agent LLM trading |
| 4 | **FinRL** | [AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL) | 10 k+ | 2025-active | Python | Reinforcement-learning trading |
| 5 | **FinGPT** | [AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | 14 k+ | 2025-active | Python | Financial LLM / NLP |
| 6 | **freqtrade** | [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | 29 k+ | 2026-active | Python | Crypto algo-trading |
| 7 | **nautilus_trader** | [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | 5 k+ | 2026-active | Python/Rust | Production trading engine |
| 8 | **qlib** | [microsoft/qlib](https://github.com/microsoft/qlib) | 14 k+ | 2025-active | Python | AI quant research platform |
| 9 | **zipline-reloaded** | [stefan-jansen/zipline-reloaded](https://github.com/stefan-jansen/zipline-reloaded) | 1 k+ | 2025-active | Python | Backtesting (Zipline reboot) |
| 10 | **vectorbt** | [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | 4 k+ | 2025-active | Python | Vectorised backtesting |
| 11 | **backtrader** | (github.com/mementum/backtrader) | 13 k+ | maintenance | Python | Event-driven backtesting |
| 12 | **lumibot** | [Lumiwealth/lumibot](https://github.com/Lumiwealth/lumibot) | 2 k+ | 2025-active | Python | Bot + backtesting, multi-asset |
| 13 | **StockSharp** | [StockSharp/StockSharp](https://github.com/StockSharp/StockSharp) | 7 k+ | 2025-active | C# | Multi-venue trading platform |
| 14 | **stockbot-on-groq** | [bklieger-groq/stockbot-on-groq](https://github.com/bklieger-groq/stockbot-on-groq) | 4 k+ | 2025-active | TypeScript/Next | LLM chatbot + TradingView |
| 15 | **Gekko** | [askmike/gekko](https://github.com/askmike/gekko) | 10 k | archived | Node.js | Crypto TA bot (DEPRECATED) |

**Not separately benchmarked** (excluded or absorbed into above): AIStockTradingBot (minimal GitHub activity), Gordon Gekko (same as Gekko node project).

---

## Dimension 1 — Asset Classes Covered

### Competitor Coverage Matrix

| Project | Equities | ETFs | Options | Futures | FX | Crypto | Commodities | Fixed Income | Alt Data |
|---------|----------|------|---------|---------|-----|--------|-------------|--------------|----------|
| OpenBB | YES | YES | YES | YES | YES | YES | YES | YES | YES |
| ai-hedge-fund | Equities only | — | — | — | — | — | — | — | — |
| TradingAgents | Equities primary | — | — | — | — | partial | — | — | — |
| FinRL | YES | YES | — | — | — | YES | — | — | partial |
| FinGPT | news/NLP layer | — | — | — | — | — | — | — | YES (social) |
| freqtrade | — | — | — | — | — | YES | — | — | — |
| nautilus_trader | YES | — | YES | YES | YES | YES | — | — | — |
| qlib | Equities (CN+US) | YES | — | — | — | — | — | — | partial |
| zipline-reloaded | YES | YES | — | — | — | — | — | — | — |
| vectorbt | YES | YES | — | — | — | YES | — | — | — |
| lumibot | YES | YES | YES | YES | YES | YES | — | — | — |
| StockSharp | YES | YES | YES | YES | YES | YES | YES | YES | — |
| stockbot-groq | YES | YES | — | — | — | YES | — | — | — |
| **Investment Agent (us)** | **YES** | **YES** | **NO** | **NO** | **NO** | **YES** | **NO** | **NO** | **partial (news)** |

**Gap analysis:**
- We cover equities, ETFs (via yfinance), and crypto (via CCXT). No options, futures, FX, commodities, or fixed income.
- For our stated "thesis-aware portfolio tool" scope, **options and futures are medium-priority gaps**; FX and commodities are lower priority given the solo-operator, personal-portfolio use case.
- Fixed income (bond yields, duration risk) is a **macro-context gap** — FRED covers some of this but we have no bond price or credit spread feed.

---

## Dimension 2 — Data Provider Integrations

### Free-Tier Provider Landscape

| Provider | What it offers | Free Tier Limits | TOS / Licensing | Projects using it |
|----------|---------------|-----------------|-----------------|-------------------|
| **Yahoo Finance (yfinance)** | OHLCV, fundamentals, news headlines | Unofficial; no formal rate limit stated; community cap ~2 req/s before 429s | Non-commercial intent; unofficial API — TOS prohibits commercial redistribution | OpenBB, FinRL, TradingAgents, vectorbt, lumibot, ai-hedge-fund, **us** |
| **FRED** | 800 k+ macro series, GDP, CPI, Fed Funds, yield curves | 120 req/min with free API key | Public-domain data; free for all uses | OpenBB, **us** |
| **CCXT** | OHLCV + order book + ticker from 150+ crypto exchanges | Exchange-specific; Binance etc. have generous free tiers | MIT license; exchange TOS apply per venue | freqtrade, nautilus_trader, vectorbt, **us** |
| **Alpha Vantage** | OHLCV, fundamentals, Forex, technicals | **25 req/day** (free); 5 req/min rate cap | Non-commercial free tier; paid from $50/mo | TradingAgents, OpenBB, StockSharp, FinRL |
| **Finnhub** | Real-time quotes, company fundamentals, insider trades, ESG, earnings transcripts, news, WebSocket streaming | **60 req/min** free; WebSocket for up to 50 symbols | Free for personal/dev use; commercial requires paid plan ($0–$299+/mo) | OpenBB (via extension) |
| **FMP (Financial Modeling Prep)** | Income/balance/cash flow statements, ratios, 25 k+ companies; earnings transcripts | **500 MB/30 days bandwidth** on free tier; ~250 calls/day practical | Non-commercial free tier; paid from $19/mo | OpenBB, ai-hedge-fund (via financialdatasets.ai) |
| **Tiingo** | Daily OHLCV, news, fundamentals; 50+ symbol/hr free | Free tier: 50 symbols/hour, 5 yr fundamentals | Free API key required; non-commercial free | OpenBB, lumibot |
| **Polygon.io** | Full tick data, aggregates, options, FX, crypto | **5 req/min**, end-of-day only | Personal/non-commercial free; paid starts $29/mo | stockbot-groq (Polygon.io), lumibot, StockSharp |
| **SimFin** | Income/balance/cashflow (quarterly + annual), 5 k US stocks | Free tier: data delayed **12 months**; 10+ yrs history | Creative Commons for individual use; commercial license required | FinRL-Trading (academic use) |
| **SEC EDGAR (edgartools)** | 10-K, 10-Q, 8-K, XBRL financial statements, insider transactions (Form 4), 13F holdings | **No rate limits, no API key** (direct EDGAR access) | Public domain US government data | OpenBB (SEC extension), none of the others listed above |
| **CoinGecko** | Crypto OHLCV, on-chain DEX data via GeckoTerminal, metadata | 5–15 req/min (demo: 30 req/min), 250 k lifetime calls | Free API key; commercial requires paid | freqtrade (optional), nautilus_trader (community adapters) |
| **MarketAux** | Financial news + pre-computed sentiment score (-1 to 1), 5 k+ sources | **100 req/day** free | Free for personal use; commercial from $9/mo | community projects |
| **Glassnode** | On-chain Bitcoin/Ethereum metrics (MVRV, SOPR, exchange flows, 900+ metrics) | Tier 1 metrics at daily resolution only; API access requires **Professional plan + API add-on** ($39+/mo) | Commercial license required for API | None of the OSS projects surveyed (too expensive) |
| **Finnhub Earnings Transcripts** | Full earnings call transcripts | Included in free 60 req/min tier | Personal use free | — |
| **QuiverQuant** | Congressional trades, insider transactions, govt contracts | Partial free; **full API $25/mo** | Non-commercial free scraping; commercial plan required for API | QuantConnect integrates it; not in OSS projects above |
| **StockTwits** | Social sentiment (bullish/bearish scores per ticker) | **1,000 req/month** free | Developer TOS; commercial use requires agreement | community projects |
| **pytrends / trendspyg** | Google Trends search interest | Unofficial scraper; **no rate limit published**; pytrends archived April 2025; trendspyg is successor | Google TOS prohibits automated scraping; use at own risk | academic projects |
| **Wikipedia Pageviews API** | Article view counts (proxy for public attention) | No API key; no rate limit stated | Creative Commons; free for any use | academic / research |
| **FinBERT (local)** | Financial sentiment inference (positive/negative/neutral) | No API; runs locally via HuggingFace transformers | Apache 2.0 | FinGPT (fine-tuning base) |

**Deprecated / gone:**
- **IEX Cloud** — shut down August 2024. Any project still referencing it needs migration. Migration target: Alpha Vantage or FMP.
- **Pushshift (Reddit)** — Reddit revoked access May 2023. Historical Reddit sentiment via Pushshift is gone.

### What We Currently Have vs. Competitors

| Provider | We Have | Competitor Baseline |
|----------|---------|---------------------|
| Yahoo Finance (yfinance) | YES — primary equity/ETF source | Ubiquitous across all |
| FRED | YES — macro agent | OpenBB + us; rare in others |
| CCXT | YES — crypto agent | freqtrade, nautilus, vectorbt, us |
| Anthropic Claude for sentiment | YES — LLM NLP on news | Unique to us; most use FinBERT or rule-based |
| Custom web scraper (news) | YES — `web_news_provider.py` | Most projects scrape or use newsAPI |
| Alpha Vantage | **NO** | TradingAgents, OpenBB, StockSharp |
| Finnhub | **NO** | OpenBB |
| FMP | **NO** | OpenBB, ai-hedge-fund |
| SEC EDGAR / edgartools | **NO** | OpenBB |
| SimFin | **NO** | FinRL-Trading |
| Tiingo | **NO** | OpenBB, lumibot |
| MarketAux (news + sentiment) | **NO** | Community |
| FinBERT local | **NO** | FinGPT, community |
| StockTwits | **NO** | Community |
| CoinGecko | **NO** | freqtrade, community |
| QuiverQuant (congressional/insider) | **NO** | QuantConnect |
| Glassnode on-chain | **NO** | No OSS project (too costly) |

---

## Dimension 3 — Caching, Rate-Limit, and Pool Strategies

### How Competitors Avoid the yfinance-Lock Bottleneck

The yfinance `_yfinance_lock` (threading.Lock held across full download+parse) is **our** pain point. Here is what the ecosystem does:

| Project | Strategy | Notes |
|---------|----------|-------|
| **freqtrade** | Uses CCXT (crypto only); configures `rateLimit` in milliseconds per exchange; async calls with `asyncio`; exponential backoff on 429 | Crypto-native — sidesteps yfinance entirely |
| **OpenBB** | Provider-agnostic abstraction with per-provider rate-limit decorators; recommends swapping yfinance for Tiingo or FMP for reliability | Architecture decouples provider from consumer |
| **nautilus_trader** | Custom Rust-level adapter per venue; Redis-backed cache for state persistence; no yfinance | Production-grade; not comparable to our stack |
| **FinRL** | Uses `yfinance.download()` multi-ticker batch (list of tickers in single call); threads=True parameter leverages yfinance's built-in thread pool | Avoids per-ticker lock serialisation by batching |
| **ai-hedge-fund** | Moved entirely to `financialdatasets.ai` (paid); bypasses yfinance | Small but pragmatic move |
| **TradingAgents** | Alpha Vantage primary; yfinance as fallback; open issues about Alpha Vantage rate limits breaking workflow | Alpha Vantage free tier (25/day) worse than yfinance |
| **lumibot** | Yahoo for backtesting; Polygon/ThetaData/Databento for production; separate data broker and execution broker abstraction | Clean abstraction model worth borrowing |
| **vectorbt** | Recommends against yfinance in production docs; uses CCXT for crypto and custom providers; supports pandas-native CSV input | Correctly warns yfinance is "demonstration only" |
| **qlib** | Custom binary data format (qlib format) with server-side caching (qlib-server); data pre-fetched and cached on disk; no yfinance in production | Most sophisticated data caching of any project surveyed |

**The consensus workaround (applicable to us):**

1. **Batch mode** — Call `yfinance.download(tickers_list, ...)` instead of per-ticker `Ticker.history()`. Built-in thread pool is safe with multi-ticker syntax; avoids our lock serialisation.
2. **Disk cache** — Save OHLCV as Parquet/SQLite; only fetch new bars incrementally (date range from last stored date to today).
3. **TTL-based in-memory cache** — Already partial in our `data_providers/cache.py`; needs TTL logic and Parquet backing.
4. **Provider swap for fundamentals** — Fundamentals (P/E, earnings) come from yfinance `Ticker.info` which is separate from `download()` and is single-threaded. Swap this to Finnhub or FMP free tier.

---

## Dimension 4 — Alternative / Unconventional Data

### Competitor Coverage

| Alt Data Type | Best OSS Coverage | Source Used | Free? | We Have? |
|---------------|------------------|-------------|-------|----------|
| On-chain Bitcoin/ETH (MVRV, SOPR, exchange flows) | **No OSS project covers this well** | Glassnode (API-paid), Messari (partial free) | Glassnode: NO (Professional plan) | **NO** |
| On-chain DEX data (liquidity pools, token OHLCV) | nautilus_trader (community adapters) | CoinGecko / GeckoTerminal | YES (30 req/min demo) | **NO** |
| Options flow / unusual options activity | None of the OSS projects | Unusual Whales ($250/mo historical) | NO — all paid | **NO** |
| Dark pool flow | None of the OSS projects | Unusual Whales, FlowAlgo (paid) | NO | **NO** |
| Congressional trades | QuantConnect (via QuiverQuant) | QuiverQuant ($25/mo API) | Partial (scraping free) | **NO** |
| Insider transactions (Form 4) | OpenBB (SEC EDGAR extension) | SEC EDGAR — free, no key | YES | **NO** |
| Google Trends (search interest) | Academic projects only | pytrends (archived Apr 2025) / trendspyg | Risky (TOS violation) | **NO** |
| Wikipedia pageviews | Academic projects only | Wikimedia REST API | YES (free, public domain) | **NO** |
| Reddit / WSB sentiment | FinGPT (training data), academic projects | PRAW (official Reddit API, free for personal use) | YES (personal use) | **NO** |
| StockTwits sentiment | Community scrapers | StockTwits API | YES (1 k req/mo free) | **NO** |
| Earnings call transcripts | OpenBB (Finnhub ext), community | Finnhub (free 60/min), FMP (bandwidth-limited) | Finnhub YES | **NO** |
| Analyst estimates (EPS, revenue) | OpenBB, lumibot | Tiingo, FMP | Tiingo YES | **NO** |
| ESG scores | OpenBB (Finnhub ext) | Finnhub (free 60/min) | YES | **NO** |
| Crypto funding rates | freqtrade, nautilus_trader | CCXT (exchange-native) | YES | **YES** (CCXT provider has funding rates) |

**Key finding on on-chain:** Glassnode is the gold standard but requires a paid subscription. The practical free-tier on-chain option is CoinGecko's GeckoTerminal (DEX OHLCV, pool data) and Messari's free API (limited). Our CONCERNS.md already flags this: `key_stats ATH may lag actual on-chain ATH by weeks`.

---

## Dimension 5 — Fundamentals Depth

### Competitor Fundamentals Capability

| Project | Income Stmt | Balance Sheet | Cash Flow | Sector P/E | ESG | Analyst Estimates | Point-in-Time? |
|---------|-------------|---------------|-----------|------------|-----|-------------------|----------------|
| OpenBB | YES (FMP, Tiingo, SEC) | YES | YES | YES (via Finviz) | YES (Finnhub) | YES | Partial (FMP historical) |
| ai-hedge-fund | YES (financialdatasets.ai) | YES | YES | NO | NO | NO | NO |
| TradingAgents | YES (Alpha Vantage) | Partial | Partial | NO | NO | NO | NO |
| FinRL-Trading | YES (Yahoo, FMP, WRDS) | YES | YES | NO | NO | NO | WRDS (paid) |
| nautilus_trader | No fundamentals focus | — | — | — | — | — | — |
| lumibot | Yahoo (limited) + Polygon | Yahoo (limited) | Yahoo (limited) | NO | NO | NO | NO |
| **Investment Agent (us)** | **YES (yfinance)** | **YES (yfinance)** | **YES (yfinance)** | **YES (static 12-sector table)** | **NO** | **NO** | **NO (look-ahead risk in backtests)** |

**Critical gap — point-in-time data:** Our `FundamentalAgent` uses yfinance which returns **current/restated** financials. Backtests using these numbers are forward-looking contaminated. CONCERNS.md flags this as high-priority: "Backtests not reliable for out-of-sample validation." The fix requires SimFin (12-month delayed free) or FMP historical (paid from $19/mo). SimFin's free 12-month delay makes it useful for research but not for current-quarter scoring.

**Sector P/E gap:** Our static 12-sector table (`SECTOR_PE_MEDIANS`) was an improvement but is hardcoded. Competitors pull live sector medians from Finviz or compute from a large universe. Finnhub's free tier exposes sector-level data that could replace our static table.

---

## Table Stakes — Must Have or Users Leave

These are capabilities that any serious investment-analysis tool is expected to have:

| Feature | Why Expected | Our Status | Complexity | Priority |
|---------|--------------|------------|------------|----------|
| Multi-equity OHLCV (daily) | Every user tracks stocks | YES (yfinance) | — | Already done |
| Crypto OHLCV | Growing asset class | YES (CCXT) | — | Already done |
| Macro context (inflation, Fed Funds, VIX) | Regime awareness is core value | YES (FRED) | — | Already done |
| Basic fundamentals (P/E, EPS, revenue) | Every fundamental investor needs this | YES (yfinance) | — | Already done |
| News sentiment | Required for thesis monitoring | YES (custom scraper + Claude) | — | Already done |
| Batch download / performance for 10+ tickers | Users will hold >5 positions | PARTIAL (serialised lock) | Medium | **High — fix bottleneck** |
| Income / balance / cash flow statements | FundamentalAgent completeness | YES (yfinance, limited) | — | Already done (basic) |
| Sector-relative P/E scoring | Standard screening technique | PARTIAL (static table) | Low | **Medium — live data upgrade** |
| Alternative free fundamentals (not just yfinance) | yfinance is unreliable and unofficial | NO | Low-Medium | **High — add Finnhub fallback** |

---

## Differentiators — Competitive Advantages Worth Building

Features that set a product apart; not expected but valued:

| Feature | Value Proposition | Complexity | Source | Our Status | Recommended Action |
|---------|-------------------|------------|--------|------------|-------------------|
| **FinBERT local sentiment** | No Claude API key needed; offline fallback for sentiment | Low (pip install + HuggingFace download) | ProsusAI/finBERT (Apache 2.0) | NO | **Add as fallback** when ANTHROPIC_API_KEY absent; reduces hard dependency on paid API |
| **SEC EDGAR insider transactions** | Form 4 filings — free, no key, legally mandated | Medium (`edgartools` library) | edgartools (Apache 2.0), EDGAR public domain | NO | Add to FundamentalAgent or new InsiderAgent; meaningful signal |
| **SimFin point-in-time fundamentals** | Removes backtest look-ahead bias (12-month delay on free tier) | Medium | SimFin (CC for individual use) | NO | Add as optional data source for backtesting mode only |
| **MarketAux news + built-in sentiment** | Pre-scored sentiment reduces Claude API usage; 5 k+ sources | Low | MarketAux (100 req/day free) | NO | Add as sentiment data source; supplement web_news_provider.py |
| **StockTwits retail sentiment** | Retail positioning signal, distinct from news sentiment | Low | StockTwits API (1 k req/mo free) | NO | Add to SentimentAgent; differentiated signal vs. news |
| **CoinGecko on-chain DEX data** | Pool flows, token OHLCV, GeckoTerminal data for DeFi tokens | Medium | CoinGecko demo (30 req/min) | NO | Add to CryptoAgent for DeFi-native tokens |
| **Earnings call transcript ingestion** | Qualitative thesis validation; LLM-ready | Medium | Finnhub free 60/min | NO | New TranscriptAgent or augment FundamentalAgent |
| **Finnhub ESG scores** | ESG-aware thesis capture | Low | Finnhub free 60/min | NO | Add ESG field to position thesis schema |
| **PRAW / Reddit WSB sentiment** | Retail momentum signal distinct from StockTwits | Medium | PRAW (official Reddit API, free personal use) | NO | New signal; but Pushshift gone — only forward-looking data |
| **Live sector P/E from Finnhub** | Replace static `SECTOR_PE_MEDIANS` table | Low | Finnhub free tier | NO | **Near-term improvement** — fixes CONCERNS.md residual risk |
| **Tiingo as yfinance fallback** | More stable API, proper rate limits, 30 yr history | Low | Tiingo (50 symbols/hr free) | NO | Add `TiingoProvider` implementing base provider interface |
| **Wikipedia pageviews signal** | Free, no key, interesting attention proxy | Low | Wikimedia REST API (public domain) | NO | Experimental; add as optional SentimentAgent feature |

---

## Anti-Features — Deliberately NOT Build

Features to explicitly exclude, with rationale:

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Glassnode on-chain integration** | No free tier; Professional plan + API add-on required; not aligned with our free-only constraint | Use CoinGecko GeckoTerminal for DEX on-chain data (free) |
| **Kaiko crypto data** | Enterprise-only; no public pricing; contact-sales only | Use CCXT + CoinGecko; sufficient for personal portfolio |
| **Unusual Whales options flow** | $250/mo for historical; not free-tier compatible | Options flow is out of scope for thesis-tracking tool |
| **Dark pool data integration** | All providers paid (FlowAlgo, Unusual Whales); execution-focused | Out of scope; we are signal/thesis, not execution |
| **Bloomberg / Refinitiv / WRDS** | Institutional-only; $10 k+/yr; incompatible with solo-operator scope | Use FMP/Tiingo free tiers for comparable data |
| **Automated order execution** | Already in PROJECT.md Out-of-Scope; multiplies regulatory/liability surface | Remain signal + thesis tool only |
| **Binance/Kraken live trading hooks** | Out of scope; freqtrade/nautilus do this better | Let user connect to broker separately |
| **pytrends Google Trends scraping** | pytrends archived April 2025; TOS prohibits automated scraping; fragile | Use Wikipedia pageviews API (legal, stable, similar signal) |
| **Pushshift Reddit historical archive** | Reddit revoked access May 2023; archive defunct | Use PRAW for forward-looking Reddit data only |
| **Real-time tick data / level 2 order book** | nautilus_trader and freqtrade cover this better; requires low-latency infra | Out of scope for daily thesis-review cadence |
| **IEX Cloud** | Shut down August 2024; deprecated | Migrate references to Tiingo or Finnhub |

---

## Specific Integration Recommendations (Priority Ordered)

### Priority 1 — Fix existing bottleneck (no new providers needed)

**1A. yfinance batch mode for multi-ticker equity downloads**
- **What:** Replace per-ticker `Ticker.history()` calls with `yfinance.download([list], ...)` which uses yfinance's built-in thread pool safely.
- **Where:** `data_providers/yfinance_provider.py`
- **Impact:** Removes the global `_yfinance_lock` for OHLCV downloads (still needed for `Ticker.info` fundamentals).
- **Effort:** Low — API-compatible change within existing provider abstraction.
- **Confidence:** HIGH (confirmed in yfinance docs and FinRL practice).

### Priority 2 — Free fundamentals fallback (Finnhub)

**2A. Add Finnhub as FundamentalAgent secondary source**
- **What:** Finnhub free tier (60 req/min) provides real-time fundamentals, sector metrics, insider trades, ESG scores, and earnings transcripts. Replace static `SECTOR_PE_MEDIANS` table with live Finnhub sector P/E.
- **Provider:** `finnhub-python` (official SDK, MIT-compatible).
- **Free tier:** 60 req/min; no daily cap; WebSocket streaming for up to 50 symbols.
- **TOS:** Free for personal/dev use; commercial requires paid plan.
- **Where:** New `data_providers/finnhub_provider.py`; integrate with `agents/fundamental.py`.
- **Effort:** Medium — write provider, update FundamentalAgent.
- **Confidence:** HIGH (Finnhub docs verified).

### Priority 3 — Local sentiment fallback (FinBERT)

**3A. FinBERT as Anthropic fallback**
- **What:** When `ANTHROPIC_API_KEY` is absent, use `ProsusAI/finbert` (HuggingFace, Apache 2.0) for sentiment inference locally. Reduces hard external dependency and API cost.
- **Dependency:** `transformers`, `torch` (already likely in Python env for other purposes, or add optional `[sentiment]` tier in pyproject.toml).
- **TOS:** Apache 2.0 — no restrictions.
- **Where:** `agents/sentiment.py` — check key, fallback to local model.
- **Effort:** Low-Medium — HuggingFace pipeline is ~10 lines.
- **Confidence:** HIGH (FinBERT on HuggingFace verified).

### Priority 4 — SEC EDGAR insider transactions

**4A. edgartools for Form 4 insider trades**
- **What:** `edgartools` Python library parses Form 4 (insider transactions), 10-K/10-Q financials, 8-K events directly from EDGAR. No API key. No rate limits. Legally public domain.
- **Signal value:** Insider buying is a documented leading indicator; no OSS project in our survey integrates this for the thesis-monitoring use case.
- **TOS:** US government public domain data; edgartools Apache 2.0.
- **Where:** New `data_providers/edgar_provider.py`; new signal in `agents/fundamental.py` or optional `agents/insider.py`.
- **Effort:** Medium — parse Form 4 structure and map to signal scoring.
- **Confidence:** HIGH (edgartools docs verified; EDGAR confirmed no key).

### Priority 5 — News sentiment augmentation (MarketAux)

**5A. MarketAux as structured news + sentiment source**
- **What:** MarketAux provides ticker-tagged financial news with pre-computed sentiment scores (-1 to 1). Supplements and can partially replace the custom web scraper.
- **Free tier:** 100 req/day. At ~5 positions in a typical portfolio, one daily cycle = 5 requests. Fits within free tier.
- **TOS:** Free for personal use; commercial from $9/mo.
- **Where:** Augment `data_providers/web_news_provider.py` or add `data_providers/marketaux_provider.py`.
- **Effort:** Low — REST API, returns JSON with sentiment field.
- **Confidence:** MEDIUM (MarketAux docs verified; sentiment field confirmed).

### Priority 6 — SimFin for backtest point-in-time fundamentals (deferred)

**6A. SimFin as optional backtest data source**
- **What:** SimFin provides quarterly/annual income, balance, cash flow statements. Free tier delayed 12 months (eliminates look-ahead bias for backtesting against older periods).
- **Free tier:** Creative Commons for individual use; 12-month delay on free.
- **TOS:** CC for individual use. Commercial requires license. Attribution required.
- **Where:** `data_providers/simfin_provider.py`; plumbed into backtesting module when `use_point_in_time=True`.
- **Effort:** Medium — `simfin` Python library available; needs integration with backtest engine.
- **Confidence:** HIGH (SimFin docs verified).
- **Note:** Deferred because the 12-month delay means it's only useful for historical backtests, not current scoring.

---

## Feature Dependencies

```
yfinance batch mode (1A) — prerequisite for: faster backtesting, larger watchlists
                           ↑
finnhub_provider (2A) → replaces static SECTOR_PE_MEDIANS → fixes CONCERNS.md residual risk
                       → enables ESG fields in thesis schema
                       → enables earnings transcript ingestion

edgartools/edgar_provider (4A) → enables InsiderAgent signal → augments FundamentalAgent confidence

FinBERT local (3A) → removes hard ANTHROPIC_API_KEY dependency → improves offline/zero-cost operation

SimFin (6A) → enables point-in-time backtest mode → reduces look-ahead bias flagged in CONCERNS.md
```

---

## MVP Recommendation

Given our existing 889-test foundation and the "free data only" constraint, prioritise:

1. **yfinance batch download** — removes the `_yfinance_lock` bottleneck; 0 new dependencies.
2. **Finnhub provider** — single free key unlocks insider data, live sector P/E, ESG, transcripts; replaces three separate future integrations.
3. **FinBERT local fallback** — eliminates the Anthropic API as a single point of failure for SentimentAgent.
4. **SEC EDGAR insider transactions** — highest signal-to-cost ratio of any alternative data source (free, no key).

Defer: CoinGecko DEX on-chain, StockTwits, Reddit/PRAW, Wikipedia pageviews, SimFin. These are differentiators worth iterating toward but not blockers for the next milestone.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Provider free-tier limits | MEDIUM | Rates from official docs (Finnhub, Alpha Vantage, MarketAux, CoinGecko) or multiple corroborating sources; yfinance limits are community-documented (unofficial API) |
| TOS / licensing | MEDIUM | Based on provider docs as of research date; subject to change; verify before commercial use |
| Project integrations (which project uses which provider) | MEDIUM | Derived from README/source review; some projects (backtrader, Gekko) not fully audited as they are maintenance-only or archived |
| Alt data accessibility | HIGH | Unusual Whales / Glassnode / Kaiko paid tiers confirmed from pricing pages; EDGAR no-key confirmed from edgartools docs |
| Caching strategies | MEDIUM | Derived from project docs and issues; freqtrade and qlib strategies well-documented; others inferred from code patterns |

---

## Sources

- OpenBB providers: https://docs.openbb.co/odp/python/extensions/providers
- ai-hedge-fund: https://github.com/virattt/ai-hedge-fund
- TradingAgents: https://github.com/TauricResearch/TradingAgents
- FinRL: https://github.com/AI4Finance-Foundation/FinRL
- freqtrade data download: https://www.freqtrade.io/en/stable/data-download/
- nautilus_trader integrations: https://nautilustrader.io/
- qlib: https://github.com/microsoft/qlib
- lumibot brokers: https://lumibot.lumiwealth.com/brokers.html
- StockSharp: https://github.com/StockSharp/StockSharp
- stockbot-on-groq: https://github.com/bklieger-groq/stockbot-on-groq
- vectorbt: https://vectorbt.dev/getting-started/features/
- Finnhub rate limits: https://finnhub.io/docs/api/rate-limit
- Finnhub pricing: https://finnhub.io/pricing
- Alpha Vantage free tier: https://www.alphavantage.co/premium/
- Alpha Vantage rate limits: https://alphalog.ai/blog/alphavantage-api-complete-guide
- Polygon.io free tier: https://polygon.io/pricing
- SimFin Python API: https://simfin.readthedocs.io/
- edgartools: https://github.com/dgunning/edgartools
- MarketAux docs: https://www.marketaux.com/documentation
- MarketAux pricing: https://www.marketaux.com/pricing
- CoinGecko free tier: https://support.coingecko.com/hc/en-us/articles/4538771776153
- CoinGecko OHLCV: https://www.coingecko.com/en/api/ohlc-data
- Glassnode API credits: https://docs.glassnode.com/basic-api/api-credits
- Glassnode pricing: https://glassnode.com/pricing/data
- Unusual Whales API: https://unusualwhales.com/public-api
- QuiverQuant API: https://api.quiverquant.com/
- FinBERT HuggingFace: https://huggingface.co/ProsusAI/finbert
- FinBERT GitHub: https://github.com/ProsusAI/finBERT
- StockTwits free tier: https://rapidapi.com/stocktwits/api/stocktwits
- IEX Cloud shutdown: https://www.alphavantage.co/iexcloud_shutdown_analysis_and_migration/
- Pushshift shutdown context: community posts, May 2023
- pytrends archived: https://github.com/flack0x/trendspyg (archived notice Apr 2025)
- Wikipedia pageviews API: https://franz101.substack.com/p/google-trends-api-alternative-wikipedia
- yfinance batch threading: https://ranaroussi.github.io/yfinance/reference/yfinance.ticker_tickers.html
- yfinance rate limit issues: https://blog.ni18.in/how-to-fix-the-yfinance-429-client-error-too-many-requests/
- Tiingo pricing: https://www.tiingo.com/pricing
- FMP free tier: https://site.financialmodelingprep.com/pricing-plans
- Kaiko institutional: https://datarade.ai/data-providers/kaiko-data/profile

---

*Research completed: 2026-04-21*
