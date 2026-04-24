#!/usr/bin/env python3
"""CLOSE-04 operator verification: TargetWeightBar browser flow.

Prints a 5-step manual checklist and prompts the operator for approval.
Pairs with the Vitest snapshot test at
frontend/src/components/portfolio/__tests__/TargetWeightBar.snapshot.test.tsx
which locks the static DOM contract; this script verifies the live
browser behavior (set/reload/clear/invalid prompt).

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
CLOSE-04: Target-Weight Browser Flow Verification
=================================================

Prerequisites — in two terminals:

  Terminal 1 (backend):
    python -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload

  Terminal 2 (frontend):
    cd frontend && npm run dev

  Browser:
    open http://localhost:3000/portfolio

Steps to verify:

  1. Pick any open position (ideally one without a target set).
     Click the 'set target' link/button under its Weight cell.
     At the prompt, enter: 0.10
     → Expected: TargetWeightBar appears with:
       - amber fill extending right IF current weight > 10%
       - green fill extending left IF current weight < 10%
       - label reading '+X.X%' (overweight) or '-X.X%' (underweight)

  2. Reload the page (Ctrl+R / Cmd+R).
     → Expected: the target persists (bar still renders with the same
       color and deviation). Confirms PATCH wrote to backend + GET
       returns target_weight in response (WR-01 fix from Phase 4).

  3. Click 'edit target' on the same position.
     At the prompt, leave the field blank and press OK.
     → Expected: bar disappears (targetWeight cleared to null).

  4. Click 'edit target' again.
     At the prompt, enter: 1.5
     → Expected: browser alert fires with message
       'Target weight must be between 0.0 and 1.0'

  5. Snapshot parity check (static DOM contract):
     cd frontend && npx vitest run src/components/portfolio/__tests__/TargetWeightBar.snapshot.test.tsx
     → Expected: 4 tests pass, no snapshot updates needed.

If all 5 steps succeed, this item is resolved.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CLOSE-04 target-weight browser verification"
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
            f"\nOK — CLOSE-04 approved {timestamp}.\n"
            f"Evidence snippet for 04-HUMAN-UAT.md:\n\n"
            f"  **result:** resolved ({timestamp} — verified via operator run "
            f"+ Vitest snapshot test frontend/src/components/portfolio/"
            f"__tests__/TargetWeightBar.snapshot.test.tsx) {note}\n"
        )
        return 0
    else:
        print(
            f"\nNOT OK — CLOSE-04 verification reported as: {decision!r}.\n"
            f"Paste the issue into .planning/milestones/v1.0-phases/"
            f"04-portfolio-ui-analytics-uplift/04-HUMAN-UAT.md item 1's "
            f"'issues:' section and re-run once fixed.\n"
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
