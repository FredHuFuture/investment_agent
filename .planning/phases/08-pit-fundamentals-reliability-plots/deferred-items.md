# Phase 8 Deferred Items

Items discovered during execution that fall outside the current task's scope. Tracked here so they can be addressed in a focused effort, not silently inherited.

## Pre-existing test-isolation flakes (discovered during 08-01)

**Symptom:** When running `pytest -q` (full suite), `tests/test_an02_drift_api.py` fails 9/9 with `RuntimeError: There is no current event loop in thread 'MainThread'`. The tests pass 9/9 when run in isolation.

**Root cause:** The `db_path` fixture at `tests/test_an02_drift_api.py:19-23` uses a synchronous fixture body that calls `asyncio.get_event_loop().run_until_complete(init_db(path))`. Under Python 3.12 / pytest-asyncio mode=auto, the event loop has already been closed/reset by the time later async tests run their setup, so `get_event_loop()` raises.

**Verification this is pre-existing:**
- Stashed Plan 08-01 changes (`db/database.py` migration, new test files), ran full suite — same 9 ERRORS reproduced.
- Re-applied Plan 08-01 changes, ran `tests/test_an02_drift_api.py` in isolation — 9/9 PASS.
- Confirmed: not introduced by Plan 08-01.

**Recommended fix (out of scope for 08-01):** Replace synchronous fixture with `@pytest_asyncio.fixture` async pattern, or use `asyncio.new_event_loop()` + cleanup. ~5-10 LOC change in `test_an02_drift_api.py` only.

**Deferred to:** A standalone test-hygiene plan or as part of a future Phase 8 plan that touches the drift API surface.

## Spurious 0-byte `investment_agent.db` at repo root

**Symptom:** A 0-byte `investment_agent.db` file is created in the project root during some pytest run (timestamp `Apr 28 20:14`, predates Plan 08-01).

**Root cause:** A test or daemon code path invokes `init_db()` without specifying `db_path`, causing the default `Path("data/investment_agent.db")` to be resolved relative to the cwd. Pre-existing.

**Recommended fix:** Add `data/*.db` patterns to `.gitignore` already exist; root-level *.db is not protected. Either:
1. Force `init_db()` to refuse a relative-default path during tests (CI-only guard).
2. Add `investment_agent.db` to `.gitignore` (root-level escape hatch).
3. Audit which test creates it and inject a `tmp_path` fixture.

**Deferred to:** Test-hygiene plan (out of 08-01 scope).
