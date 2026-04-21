# Coding Conventions

**Analysis Date:** 2026-04-21

## Naming Patterns

**Files:**
- React components: PascalCase (e.g., `ErrorAlert.tsx`, `Button.tsx`, `DataTable.tsx`)
- Utility modules: camelCase (e.g., `useApi.ts`, `formatters.ts`, `cache.ts`)
- Test files: mirror source with `.test.ts` or `.test.tsx` suffix
- Python modules: snake_case (e.g., `technical.py`, `base.py`, `models.py`)

**Functions/Exports:**
- React components: Named PascalCase exports
- Utilities: Named camelCase exports (e.g., `formatCurrency`, `formatPct`, `apiGet`, `apiPost`)
- Async functions: camelCase with async/await pattern
- Private functions: Leading underscore for internal/helper functions (e.g., `_safe_last`, `_to_float`, `_validate_asset_type`)
- Python private methods: Single underscore prefix (e.g., `_validate_asset_type`, `_clamp_confidence`)

**Variables:**
- camelCase for JavaScript/TypeScript locals and parameters
- UPPER_CASE for constants
- Numeric subscripts with underscores for separators (e.g., `1_000_000`, `30_000`)
- State variables: descriptive camelCase (e.g., `lastUpdated`, `stale`, `cacheKey`)

**Types:**
- Interfaces: PascalCase with Props suffix for component props (e.g., `ButtonProps`, `ErrorAlertProps`, `UseApiOptions`)
- Enums: PascalCase (e.g., `Signal`, `Regime`)
- Generic type parameters: Single letter or PascalCase (e.g., `<T>`, `<TestRow>`)

## Code Style

**Formatting:**
- TypeScript/React: Inferred from tsconfig (ES2020 target, strict mode)
- Indentation: 2 spaces (based on package.json and file structure)
- Line length: Inferred pragmatic from codebase, no hard limit detected

**Linting:**
- No explicit `.eslintrc` found at project root or `frontend/` level
- TypeScript strict mode enforced: `"strict": true` in `tsconfig.json`
- Unused variable detection: `"noUnusedLocals": true`, `"noUnusedParameters": true`
- Strict array indexing: `"noUncheckedIndexedAccess": true`
- No fallthrough cases: `"noFallthroughCasesInSwitch": true`

**Python:**
- `from __future__ import annotations` at top of all modules for PEP 563 compatibility
- Type hints required for function parameters and returns
- Uses stdlib `logging` module for logging
- Async/await pattern throughout (not callback-based)

## Import Organization

**TypeScript/React order:**
1. React and external library imports
2. Internal absolute path imports (using `@/` alias)
3. Relative imports (util functions, types)
4. Type imports use inline `type` keyword where appropriate

**Examples from codebase:**
```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import { getCached, setCache, isStale } from "../lib/cache";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
```

**Path Aliases:**
- `@/*` maps to `src/` in `frontend/`
- No path aliases in Python code (uses relative imports from package root)

**Python import style:**
```python
from __future__ import annotations
import asyncio
from pathlib import Path
from agents.base import BaseAgent
from agents.models import AgentInput, AgentOutput, Signal
```

## Error Handling

**TypeScript/Frontend:**
- Custom `ApiError` class extends Error with status, code, detail fields (see `src/api/client.ts`)
- Error responses follow envelope pattern with `error` field containing `code`, `message`, `detail`
- Graceful degradation: cache stale data on error, display error message to user
- Validation before render (e.g., `result.current.error` checked in state)

**Python:**
- Explicit exception handling: `try/except` blocks with specific exception types
- Use `raise ValueError()`, `raise NotImplementedError()` with descriptive messages
- Warnings accumulated in list and returned with output (e.g., `output.warnings`)
- Data validation in `__post_init__` (dataclass validation, e.g., `confidence` must be 0-100)
- Graceful fallbacks: catch exceptions, log, continue (e.g., weekly data unavailable in TechnicalAgent)

**Pattern:**
```python
try:
    weekly_df = await self._provider.get_price_history(...)
except Exception as exc:
    warnings.append(f"Weekly data unavailable: {exc}")
    weekly_df = None
```

## Logging

**Framework:** 
- Python: stdlib `logging` module
- TypeScript: No global logging library; uses browser console (inferred from codebase)

**Patterns:**
- Python agents log via `self._logger = logging.getLogger(f"investment_agent.{self.name}")`
- Use `logger.info()`, `logger.warning()` for key events
- Log before processing: "Analyzing %s" when analyzing a ticker
- Frontend: Error states and user feedback via state (not console logging)

## Comments

**When to Comment:**
- JSDoc/TSDoc for public APIs and complex utility functions
- Inline comments for non-obvious algorithmic decisions
- Block comments for complex logic sections (e.g., cache stale-while-revalidate explanation)

**JSDoc/TSDoc:**
- Used on public functions with parameters and return types documented
- Example from `useApi.ts`:
```typescript
/**
 * Generic data-fetching hook with optional caching.
 *
 * Without `cacheKey`: behaves exactly as before (fetch on every mount).
 * With `cacheKey`: stale-while-revalidate pattern.
 */
export function useApi<T>(...)
```
- Interface properties documented with inline comments explaining purpose

## Function Design

**Size:** 
- Keep functions focused and small (most utilities 10-50 lines)
- Complex agents (technical, fundamental) may span 100+ lines but decompose logic into sections

**Parameters:**
- Prefer destructuring for multiple parameters or options
- Use options objects for function overloads (e.g., `UseApiOptions` with `cacheKey` and `ttlMs`)
- Type all parameters explicitly

**Return Values:**
- Explicit return type annotations on all functions
- Return wrapped envelopes (API responses): `{ data: T, warnings: string[] }`
- Python dataclasses for complex returns (e.g., `AgentOutput`)
- Nullable returns use `T | null` or `Optional[T]`

## Module Design

**Exports:**
- Named exports preferred over default exports
- React components often use `export default` for single-component files
- Utility modules use named exports (e.g., `export function apiGet<T>(...)`)

**Barrel Files:**
- `__init__.py` in Python packages (e.g., `agents/__init__.py`)
- No explicit barrel exports detected in frontend (but could be added)

**Module Structure:**
- Components in `frontend/src/components/` organized by domain (`shared/`, `ui/`, `pages/`)
- Utilities in `frontend/src/lib/` and `frontend/src/hooks/`
- Tests in `__tests__/` subdirectories at same level as source
- Python packages at root: `agents/`, `api/`, `db/`, `portfolio/`, etc.

---

*Convention analysis: 2026-04-21*
