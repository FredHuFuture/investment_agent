# Testing Patterns

**Analysis Date:** 2026-04-21

## Test Framework

**Runner:**
- Frontend: Vitest 2.1.8
- Config: `frontend/vite.config.ts`
- Backend: pytest 8.0+
- Config: `pyproject.toml` with `[tool.pytest.ini_options]`

**Assertion Library:**
- Frontend: Vitest assertions + `@testing-library/jest-dom` (extends expect with DOM matchers)
- Backend: pytest native assertions and `pytest.approx()`

**Run Commands:**
```bash
# Frontend
npm run test          # Run all tests once
npm run test:watch   # Watch mode with hot reload

# Backend (from root)
pytest                # Run all tests
pytest -v             # Verbose output
pytest tests/         # Run specific test directory
pytest -k marker      # Run tests matching marker
```

## Test File Organization

**Location:**
- Frontend: Co-located in `__tests__/` subdirectories
  - `src/components/shared/__tests__/`
  - `src/components/ui/__tests__/`
  - `src/hooks/__tests__/`
  - `src/lib/__tests__/`
  - `src/pages/__tests__/`
  - `src/api/__tests__/`
- Backend: Centralized in `tests/` directory at root

**Naming:**
- Frontend: `ComponentName.test.tsx` for components, `moduleName.test.ts` for utilities
- Backend: `test_NNN_description.py` (numbered prefix for execution order, e.g., `test_001_db.py`, `test_005_technical_agent.py`)

**Structure:**
```
frontend/src/
├── components/
│   ├── shared/
│   │   ├── ErrorAlert.tsx
│   │   └── __tests__/
│   │       └── ErrorAlert.test.tsx
│   └── ui/
│       ├── Button.tsx
│       └── __tests__/
│           └── Button.test.tsx
└── hooks/
    ├── useApi.ts
    └── __tests__/
        └── useApi.test.ts

tests/
├── test_001_db.py
├── test_003_portfolio.py
├── test_005_technical_agent.py
├── test_009_e2e.py
└── ...
```

## Test Structure

**Suite Organization:**
```typescript
// Frontend pattern
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";

describe("ComponentName", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does something specific", () => {
    // Arrange
    const fixture = ...;
    
    // Act
    const result = ...;
    
    // Assert
    expect(result).toBe(...);
  });

  it("handles error case", async () => {
    const user = userEvent.setup();
    render(<Component />);
    await user.click(screen.getByText("Button"));
    expect(handleFn).toHaveBeenCalled();
  });
});
```

**Python pattern:**
```python
def test_specific_behavior(tmp_path: Path) -> None:
    async def _run() -> None:
        # Setup
        manager = await _create_manager(tmp_path / "test.db")
        await manager.add_position("MSFT", "stock", 200.0, 415.50, "2026-02-10")
        
        # Act
        portfolio = await manager.load_portfolio()
        
        # Assert
        assert len(portfolio.positions) == 1
        assert portfolio.cash == expected_value
    
    asyncio.run(_run())
```

**Patterns:**
- Setup/Arrange: Create test data, initialize mocks
- Execution/Act: Call function or render component
- Verification/Assert: Check results with expect or assert
- `beforeEach` for test isolation (clear mocks)
- `waitFor` for async operations in React tests
- `userEvent.setup()` for simulating user interactions

## Mocking

**Framework:** 
- Frontend: `vi` (vitest mocking utilities)
- Backend: Custom mock classes (e.g., `MockProvider` in test files)

**Patterns:**
```typescript
// Frontend mocking pattern
vi.mock("../../lib/cache", () => ({
  getCached: vi.fn(() => null),
  setCache: vi.fn(),
  isStale: vi.fn(() => true),
  DEFAULT_TTL_MS: 30_000,
}));

// Mock function assertions
const handleRetry = vi.fn();
render(<ErrorAlert message="error" onRetry={handleRetry} />);
expect(handleRetry).toHaveBeenCalledTimes(1);
expect(handleRetry).toHaveBeenCalledWith(expectedArg);

// Promise mocking
const fetcher = vi.fn().mockResolvedValue({
  data: { id: 1 },
  warnings: [],
});

const fetcher = vi.fn().mockRejectedValue(new Error("fail"));
```

**Python pattern:**
```python
class MockProvider(DataProvider):
    def __init__(self, daily_df: pd.DataFrame, weekly_df: pd.DataFrame | None = None):
        self._daily_df = daily_df
        self._weekly_df = weekly_df if weekly_df is not None else daily_df.iloc[::5]

    async def get_price_history(
        self, ticker: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        if interval == "1wk":
            return self._weekly_df
        return self._daily_df
```

**What to Mock:**
- External API calls (fetch, HTTP requests)
- Date/time functions for deterministic tests
- Cache layer functions
- Data providers in agent tests

**What NOT to Mock:**
- Database operations (use `tmp_path` fixture for isolated DB)
- Business logic core functions (test real behavior)
- Standard library functions unless testing specific error paths

## Fixtures and Factories

**Test Data:**
```typescript
// Frontend
const testData: TestRow[] = [
  { id: 1, name: "Alpha", value: 30 },
  { id: 2, name: "Beta", value: 10 },
];

// Factory for dynamic creation
const columns: Column<TestRow>[] = [
  {
    key: "name",
    header: "Name",
    render: (r) => r.name,
    sortValue: (r) => r.name,
  },
];
```

```python
# Python helper functions
def _make_ohlcv(prices: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    if volumes is None:
        volumes = [1_000_000.0 for _ in prices]
    now = datetime.now(timezone.utc)
    dates = [now - timedelta(days=(len(prices) - i)) for i in range(len(prices))]
    close = pd.Series(prices, index=pd.to_datetime(dates))
    return pd.DataFrame({
        "Open": close * 0.995,
        "High": close * 1.01,
        "Low": close * 0.99,
        "Close": close,
        "Volume": volumes,
    }, index=pd.to_datetime(dates))

async def _create_manager(db_file: Path) -> PortfolioManager:
    await init_db(db_file)
    return PortfolioManager(db_file)
```

**Location:**
- Frontend: Inline in test files at top or in `describe` block
- Backend: Helper functions `_make_*` and `_run_*` defined in test modules
- Python: Use `tmp_path` pytest fixture for isolated database files

## Coverage

**Requirements:** 
- Not explicitly enforced (no coverage config in `pyproject.toml`)
- Frontend: No coverage threshold detected
- Backend: No coverage threshold detected

**View Coverage:**
```bash
# Backend (if coverage installed)
pytest --cov=agents --cov=portfolio --cov=db tests/

# Frontend (if configured in vite.config.ts)
npm run test -- --coverage
```

## Test Types

**Unit Tests:**
- Scope: Individual functions, hooks, components in isolation
- Approach: Mock external dependencies, test single responsibility
- Examples: `formatters.test.ts` (pure functions), `useApi.test.ts` (hook behavior)
- Backend: Agent analysis with mock data providers

**Integration Tests:**
- Scope: Multiple modules working together
- Approach: Real database (via `tmp_path`), real data flow
- Examples: `test_003_portfolio.py` (manager + DB), `test_005_technical_agent.py` (agent + mock provider)
- Backend: Agents with realistic signal generation

**E2E Tests:**
- Framework: Not explicitly configured (noted as `test_009_e2e.py` exists)
- Approach: Full workflow testing (if implemented)
- Status: Placeholder test file exists; extent unclear from codebase

## Common Patterns

**Async Testing (Frontend):**
```typescript
it("fetches data on mount", async () => {
  const fetcher = vi.fn().mockResolvedValue({
    data: "success",
    warnings: [],
  });

  const { result } = renderHook(() => useApi(fetcher));

  await waitFor(() => {
    expect(result.current.loading).toBe(false);
  });

  expect(result.current.data).toBe("success");
});
```

**Async Testing (Backend):**
```python
def test_database_flow(tmp_path: Path) -> None:
    async def _run_db_flow(db_file: Path) -> None:
        await init_db(db_file)
        async with aiosqlite.connect(db_file) as conn:
            # Database operations
            await conn.execute(...)
            result = await (await conn.execute(...)).fetchone()
            assert result == expected
    
    asyncio.run(_run_db_flow(tmp_path / "test.db"))
```

**Error Testing (Frontend):**
```typescript
it("sets error message when fetch fails", async () => {
  const fetcher = vi.fn().mockRejectedValue(new Error("Network failure"));

  const { result } = renderHook(() => useApi(fetcher));

  await waitFor(() => {
    expect(result.current.loading).toBe(false);
  });

  expect(result.current.error).toBe("Network failure");
  expect(result.current.data).toBeNull();
});
```

**Error Testing (Backend):**
```python
def test_missing_data_raises_error() -> None:
    provider = MockProvider(pd.DataFrame())  # Empty
    agent = TechnicalAgent(provider)
    
    with pytest.raises(ValueError, match="No price history"):
        asyncio.run(agent.analyze(AgentInput(ticker="TEST")))
```

**User Interaction Testing:**
```typescript
it("handles button click correctly", async () => {
  const handleClick = vi.fn();
  const user = userEvent.setup();
  
  render(<Button onClick={handleClick}>Click me</Button>);
  
  await user.click(screen.getByText("Click me"));
  
  expect(handleClick).toHaveBeenCalledOnce();
});
```

## Test Markers

**Backend:**
From `pyproject.toml`:
```
markers = [
    "network: requires network access",
]
```

Usage: `@pytest.mark.network` for tests requiring external API access.

## Setup Configuration

**Frontend vitest setup:**
- File: `frontend/src/test/setup.ts`
- Imports: `@testing-library/jest-dom` (adds custom matchers)
- Environment: `jsdom` (browser-like DOM)
- Globals: `true` (vitest globals like `describe`, `it`, `expect` available without imports)
- CSS: `true` (load CSS during tests)

**Backend pytest setup:**
- Async mode: `asyncio_mode = "auto"` (pytest-asyncio)
- Test paths: `tests/` directory
- Fixtures: `tmp_path` (pytest built-in), custom managers and helpers

---

*Testing analysis: 2026-04-21*
