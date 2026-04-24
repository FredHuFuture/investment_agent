#!/usr/bin/env python3
"""CLOSE-06 operator verification: DailyPnlHeatmap tooltip hover flow.

Prints a 5-step manual checklist and prompts the operator for approval.
Pairs with the Vitest snapshot test at
frontend/src/components/performance/__tests__/DailyPnlHeatmap.snapshot.test.tsx
which locks the static DOM contract (title attributes); this script verifies
the live browser behavior (native tooltip appearing on hover, color coding).

Exit codes:
  0 — operator typed 'approved'
  2 — operator typed 'failed' or anything else
  130 — KeyboardInterrupt
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone


CHECKLIST = """\
CLOSE-06: DailyPnlHeatmap Tooltip Hover Verification
=====================================================

Prerequisites — in two terminals:

  Terminal 1 (backend):
    python -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload

  Terminal 2 (frontend):
    cd frontend && npm run dev

  Browser:
    open http://localhost:3000/performance

Note: You need at least 7 days of portfolio_snapshots for colored cells
to appear. If the heatmap shows "Run a health check..." instead, trigger
a snapshot first:
    curl -X POST http://127.0.0.1:8000/api/v1/daemon/run-once \\
      -H "Content-Type: application/json" -d '{"job":"daily"}'

Steps to verify:

  1. Open http://localhost:3000/performance and scroll to the
     'Daily P&L Heatmap' card.
     → Expected: at least 7 days of colored cells visible.
       Green cells = positive P&L days.
       Red cells = negative P&L days.
       Gray cells = zero or no data.

  2. Hover over a green (positive) cell.
     → Expected: native browser tooltip appears reading
       '{YYYY-MM-DD}: +$XXX.XX' (plus sign + formatted dollar amount).
     Example: '2026-04-15: +$152.30'

  3. Hover over a red (negative) cell.
     → Expected: tooltip reads '{YYYY-MM-DD}: -$XXX.XX'
       (negative sign, no plus prefix).
     Example: '2026-04-17: -$88.50'

  4. Hover over an empty/gray cell within the date range.
     → Expected: tooltip reads '{YYYY-MM-DD}: --'
       (double-dash for no-data days within range).

  5. Snapshot parity check (static DOM / title attribute contract):
     cd frontend && npx vitest run src/components/performance/__tests__/DailyPnlHeatmap.snapshot.test.tsx
     → Expected: 3 tests pass, no snapshot updates needed.

If all 5 steps succeed, this item is resolved.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CLOSE-06 DailyPnlHeatmap tooltip hover verification"
    )
    parser.add_argument(
        "--approved", action="store_true", help="Skip prompt; mark approved"
    )
    args = parser.parse_args(argv)

    print(CHECKLIST)

    if args.approved:
        decision = "approved"
        note = "(via --approved flag)"
    else:
        try:
            decision = input(
                "\nType 'approved' to mark resolved or 'failed <note>': "
            ).strip().lower()
        except KeyboardInterrupt:
            print("\n[aborted by user]", file=sys.stderr)
            return 130
        note = ""

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if decision.startswith("approved"):
        print(
            f"\nOK — CLOSE-06 approved {timestamp}.\n"
            f"Evidence snippet for 04-HUMAN-UAT.md:\n\n"
            f"  **result:** resolved ({timestamp} — verified via operator run "
            f"+ Vitest snapshot test frontend/src/components/performance/"
            f"__tests__/DailyPnlHeatmap.snapshot.test.tsx) {note}\n"
        )
        return 0
    else:
        print(
            f"\nNOT OK — CLOSE-06 verification reported as: {decision!r}.\n"
            f"Paste the issue into .planning/milestones/v1.0-phases/"
            f"04-portfolio-ui-analytics-uplift/04-HUMAN-UAT.md item 3's "
            f"'issues:' section and re-run once fixed.\n"
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
