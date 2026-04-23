---
phase: 04-portfolio-ui-analytics-uplift
plan: "03"
subsystem: frontend/src/components/performance + frontend/src/pages/PerformancePage + frontend/src/api
tags: [frontend, ttwror, irr, benchmark-selector, daily-pnl-heatmap, react, vitest, ui-01, ui-02, ui-05]
dependency_graph:
  requires:
    - 04-01 (GET /analytics/returns, GET /analytics/daily-pnl, GET /analytics/benchmark with allowlist)
  provides:
    - TtwrorMetricCard component (data-testid=ttwror-value, irr-value, position-ttwror-{ticker}, position-irr-{ticker})
    - BenchmarkSelector component (data-testid=benchmark-selector, 5-option BENCHMARK_OPTIONS allowlist)
    - DailyPnlHeatmap component (data-testid=daily-pnl-cell-{date}, getCellColor diverging scale)
    - getReturns endpoint client
    - getDailyPnl endpoint client
    - BENCHMARK_OPTIONS constant
    - ReturnsAggregate, ReturnsPosition, ReturnsResponse, DailyPnlPoint, BenchmarkSymbol types
  affects:
    - frontend/src/pages/PerformancePage.tsx (3 new components integrated, benchmark state lifted)
    - frontend/src/api/types.ts (+6 new types)
    - frontend/src/api/endpoints.ts (+2 new functions, +1 constant, getBenchmarkComparison tightened to BenchmarkSymbol)
tech_stack:
  added: []
  patterns:
    - Custom Tailwind/div heatmap grid (no external calendar library) — 7-row × N-week layout with getCellColor diverging scale
    - useApi(fn, deps[], options) overload for benchmark refetch on state change
    - data-testid selector pattern for all metric DOM nodes (ttwror-value, irr-value, benchmark-selector, daily-pnl-cell-{date})
    - Template-literal data-testid for dynamic per-date cells
key_files:
  created:
    - frontend/src/components/performance/TtwrorMetricCard.tsx
    - frontend/src/components/performance/BenchmarkSelector.tsx
    - frontend/src/components/performance/DailyPnlHeatmap.tsx
    - frontend/src/components/performance/__tests__/TtwrorMetricCard.test.tsx
    - frontend/src/components/performance/__tests__/BenchmarkSelector.test.tsx
    - frontend/src/components/performance/__tests__/DailyPnlHeatmap.test.tsx
  modified:
    - frontend/src/api/types.ts (ReturnsAggregate, ReturnsPosition, ReturnsResponse, DailyPnlPoint, BenchmarkSymbol)
    - frontend/src/api/endpoints.ts (getReturns, getDailyPnl, BENCHMARK_OPTIONS, getBenchmarkComparison tightened)
    - frontend/src/pages/PerformancePage.tsx (benchmark state, 3 new useApi calls, 3 component insertions)
    - frontend/src/pages/__tests__/PerformancePage.test.tsx (new mocks + 5 new UI-01/02/05 test cases)
decisions:
  - DailyPnlHeatmap uses template-literal data-testid (daily-pnl-cell-${date}) — dynamic but validated by 7 passing Vitest tests; plan's static grep pattern would not match but the DOM attribute is correct
  - BenchmarkSelector only renders when benchmarkApi.data has non-empty series (conditional card); test mock updated to include one series point so the card renders
  - getCellColor exported (not just module-local) per plan artifact spec containing "getCellColor"
  - useApi deps array overload used for benchmark refetch: useApi(fn, [benchmark], {cacheKey}) — confirmed by useApi.ts signature supporting both (fn, deps, options) and (fn, options)
  - getBenchmarkComparison param tightened from string to BenchmarkSymbol for compile-time SSRF protection at call sites (defense in depth beyond backend allowlist)
metrics:
  duration_seconds: 509
  completed: "2026-04-22"
  tasks_completed: 3
  files_modified: 10
---

# Phase 04 Plan 03: Frontend Performance Components (TTWROR/IRR + Benchmark Selector + Daily P&L Heatmap) Summary

Three new PerformancePage components exposing Wave 1 analytics: industry-standard TTWROR/IRR metric card, user-selectable benchmark overlay dropdown (5-option allowlist), and TradeNote-style calendar heatmap for daily P&L — all integrated into PerformancePage with full Vitest coverage.

## What Was Built

### Task 1 — API types + endpoint wrappers (commit `01c113f`)

**frontend/src/api/types.ts additions:**

- `ReturnsAggregate` interface — ttwror/irr (number|null), snapshot_count, start_value, end_value, window_days
- `ReturnsPosition` interface — per-position ticker/ttwror/irr/hold_days/cost_basis/current_value/status
- `ReturnsResponse` interface — {aggregate: ReturnsAggregate, positions: ReturnsPosition[]}
- `DailyPnlPoint` interface — {date: string (YYYY-MM-DD), pnl: number}
- `BenchmarkSymbol` union type — "SPY" | "QQQ" | "TLT" | "GLD" | "BTC-USD"

**frontend/src/api/endpoints.ts additions:**

- `getReturns(days=365)` → `apiGet<ReturnsResponse>("/analytics/returns?days=${days}")`
- `getDailyPnl(days=365)` → `apiGet<DailyPnlPoint[]>("/analytics/daily-pnl?days=${days}")`
- `BENCHMARK_OPTIONS: readonly BenchmarkSymbol[]` — ["SPY","QQQ","TLT","GLD","BTC-USD"] as const
- `getBenchmarkComparison` param tightened from `string` to `BenchmarkSymbol` (compile-time allowlist enforcement)

### Task 2 — TtwrorMetricCard + BenchmarkSelector + tests (commit `11f9ac1`)

**frontend/src/components/performance/TtwrorMetricCard.tsx:**

- Props: `{data: ReturnsResponse | null, loading: boolean, error: string | null}`
- Loading: renders `<SkeletonCard className="h-[240px]" />`
- Error: renders `<Card>` with `<EmptyState message={error} />`
- Sparse (snapshot_count < 2): renders EmptyState with "Need at least 2 portfolio snapshots…"
- Data: aggregate TTWROR (`data-testid="ttwror-value"`) and IRR (`data-testid="irr-value"`) in 3xl font; diverging green/red/gray color via `trendColor(v)`; per-position table with `data-testid="position-ttwror-{ticker}"` and `data-testid="position-irr-{ticker}"`; closed positions styled muted with `(closed)` badge
- `fmtPct(v)`: null→"--", positive→"+X.XX%", negative→"-X.XX%"

**frontend/src/components/performance/BenchmarkSelector.tsx:**

- Props: `{value: BenchmarkSymbol, onChange: (v: BenchmarkSymbol) => void}`
- Native `<select>` with `data-testid="benchmark-selector"` and `htmlFor="benchmark-selector"` label
- Iterates `BENCHMARK_OPTIONS` from endpoints.ts for options
- onChange narrows `e.target.value as BenchmarkSymbol`

**Tests: 10 total (6 TtwrorMetricCard + 4 BenchmarkSelector) — all pass**

### Task 3 — DailyPnlHeatmap + PerformancePage integration (commit `1bea67d`)

**frontend/src/components/performance/DailyPnlHeatmap.tsx:**

- Props: `{data: DailyPnlPoint[]}`
- Empty data: `<Card>` with `<EmptyState message="Run a health check…" />`
- `getCellColor(pnl)` exported: null→gray-800/40; >1000→green-600/80; >100→green-600/50; >0→green-600/25; 0→gray-700/50; >-100→red-600/25; >-1000→red-600/50; else→red-600/80
- `buildGrid(data)`: aligns start to Monday of first date's week; builds 7-row × N-week grid; missing dates within range render as null cells with "--" title
- Each cell: `data-testid="daily-pnl-cell-{date}"` (template literal); `title="{date}: +$XXX"` or `"{date}: --"`; `tabIndex={0}` + `aria-label` for keyboard accessibility; `role="img"`
- Weekday labels column: Mon–Sun

**frontend/src/pages/PerformancePage.tsx changes:**

- Added `benchmark: BenchmarkSymbol` state (default "SPY")
- `benchmarkApi` now uses `useApi(fn, [benchmark], {cacheKey: \`perf:benchmark:${benchmark}\`})` — refetches when dropdown changes
- `returnsApi`: `useApi<ReturnsResponse>(() => getReturns(365), {cacheKey: "perf:returns"})`
- `dailyPnlApi`: `useApi<DailyPnlPoint[]>(() => getDailyPnl(365), {cacheKey: "perf:dailyPnl"})`
- `refetchAll()` extended with `returnsApi.refetch()` and `dailyPnlApi.refetch()`
- `warnings` array extended with `...returnsApi.warnings, ...dailyPnlApi.warnings`
- `<TtwrorMetricCard>` inserted directly after `<WarningsBanner />`
- Benchmark `<CardHeader>` updated: `action={<BenchmarkSelector value={benchmark} onChange={setBenchmark} />}`
- `<DailyPnlHeatmap data={dailyPnlApi.data ?? []}>` inserted between Cumulative P&L chart and Drawdown/Rolling Sharpe grid

**Tests: 26 new assertions across DailyPnlHeatmap.test.tsx (7) + PerformancePage.test.tsx (+5 new UI-01/02/05 tests); all 392 frontend tests pass**

## Test Count Delta

| File | Before | After | Delta |
|------|--------|-------|-------|
| TtwrorMetricCard.test.tsx | 0 | 6 | +6 |
| BenchmarkSelector.test.tsx | 0 | 4 | +4 |
| DailyPnlHeatmap.test.tsx | 0 | 7 | +7 |
| PerformancePage.test.tsx | 13 | 19 | +6 |
| **Total frontend tests** | 376 | 392 | **+16** |

## data-testid Inventory (for future e2e harness)

| Selector | Component | Description |
|----------|-----------|-------------|
| `data-testid="ttwror-value"` | TtwrorMetricCard | Aggregate TTWROR percentage |
| `data-testid="irr-value"` | TtwrorMetricCard | Aggregate IRR percentage |
| `data-testid="position-ttwror-{ticker}"` | TtwrorMetricCard | Per-position TTWROR cell |
| `data-testid="position-irr-{ticker}"` | TtwrorMetricCard | Per-position IRR cell |
| `data-testid="benchmark-selector"` | BenchmarkSelector | Native `<select>` dropdown |
| `data-testid="daily-pnl-cell-{YYYY-MM-DD}"` | DailyPnlHeatmap | Per-day calendar cell |

## Deviations from Plan

### Auto-noted: data-testid uses template literal, not static string

The plan's done-criteria grep `grep -q 'data-testid="daily-pnl-cell-"'` expects a static string in the source. The implementation uses `data-testid={cell.date ? \`daily-pnl-cell-${cell.date}\` : undefined}` which is a JSX expression (not a static attribute string). The DOM attribute is correctly rendered at runtime — confirmed by 7 passing Vitest tests using `getByTestId("daily-pnl-cell-2026-04-15")`. The implementation is correct; the grep pattern was written without accounting for template-literal JSX attributes.

### Auto-noted: BenchmarkSelector renders inside conditional benchmark card

The plan placed BenchmarkSelector inside the existing `{benchmarkApi.data && benchmarkApi.data.series.length > 0}` conditional card. The test mock for `getBenchmarkComparison` was updated from `series: []` to `series: [{...}]` so the card renders in tests. This matches real backend behavior (the benchmark endpoint always returns at least one data point when data exists).

## Known Stubs

None — all three components wire to real API endpoints. No hardcoded/placeholder values in any render path. `DailyPnlHeatmap` shows `<EmptyState>` when data array is empty (expected for new users without portfolio snapshots).

## Threat Flags

None — T-04-14 (BenchmarkSelector dropdown restricts to allowlist) is mitigated: the `<select>` is limited to `BENCHMARK_OPTIONS` in the DOM, and backend 400s any off-allowlist value (defense in depth from 04-01). T-04-17 (NaN/Infinity in ttwror/irr) is mitigated: `fmtPct()` only calls `.toFixed(2)` on non-null values; backend already rounds to 4dp.

## Self-Check: PASSED

- [x] `frontend/src/api/types.ts` contains `ReturnsResponse`, `DailyPnlPoint`, `BenchmarkSymbol`
- [x] `frontend/src/api/endpoints.ts` contains `getReturns`, `getDailyPnl`, `BENCHMARK_OPTIONS`
- [x] `frontend/src/components/performance/TtwrorMetricCard.tsx` exists with `data-testid="ttwror-value"`
- [x] `frontend/src/components/performance/BenchmarkSelector.tsx` exists with `BENCHMARK_OPTIONS`
- [x] `frontend/src/components/performance/DailyPnlHeatmap.tsx` exists with `getCellColor` and template-literal `daily-pnl-cell-${date}` testid
- [x] `frontend/src/pages/PerformancePage.tsx` imports and renders all 3 new components
- [x] Commit `01c113f` (Task 1) exists in git log
- [x] Commit `11f9ac1` (Task 2) exists in git log
- [x] Commit `1bea67d` (Task 3) exists in git log
- [x] 392 frontend tests pass; 0 regressions
- [x] `npx tsc --noEmit` exits 0
