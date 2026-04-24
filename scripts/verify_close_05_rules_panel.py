#!/usr/bin/env python3
"""CLOSE-05 operator verification: AlertRulesPanel daemon-wiring flow.

Prints a 5-step manual checklist and prompts the operator for approval.
Pairs with the Vitest snapshot test at
frontend/src/components/monitoring/__tests__/AlertRulesPanel.snapshot.test.tsx
which locks the static DOM contract; this script verifies the live
browser behavior (Built-in badges, toggle persistence, daemon log exclusion).

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
CLOSE-05: MonitoringPage Rules Panel Daemon Wiring Verification
===============================================================

Prerequisites — in two terminals:

  Terminal 1 (backend):
    python -m uvicorn api.app:app --host 127.0.0.1 --port 8000 --reload

  Terminal 2 (frontend):
    cd frontend && npm run dev

  Browser:
    open http://localhost:3000/monitoring

Steps to verify:

  1. Open http://localhost:3000/monitoring
     → Expected: 5 hardcoded rules visible with 'Built-in' badges:
       STOP_LOSS_HIT, TARGET_HIT, TIME_OVERRUN,
       SIGNIFICANT_LOSS, SIGNIFICANT_GAIN.
       Delete buttons should NOT appear on these rows.
       Custom user-created rules (if any) appear below with delete buttons.

  2. Click the toggle on STOP_LOSS_HIT to disable it.
     → Expected: toggle flips to disabled state (gray background).
     Reload the page.
     → Expected: STOP_LOSS_HIT remains disabled after reload (confirms
       PATCH /api/v1/alert-rules/{id}/toggle persisted the change).

  3. Run a monitor check:
       curl -X POST http://127.0.0.1:8000/api/v1/monitor/check
     Watch the backend log (Terminal 1).
     → Expected log line (approximate format):
       Enabled hardcoded alert types:
         ['SIGNIFICANT_GAIN', 'SIGNIFICANT_LOSS', 'TARGET_HIT', 'TIME_OVERRUN']
       (STOP_LOSS_HIT should be ABSENT from this list.)

  4. Re-enable STOP_LOSS_HIT via toggle; reload; run curl again.
     → Expected: STOP_LOSS_HIT reappears in the log line.

  5. Snapshot parity check (static DOM contract):
     cd frontend && npx vitest run src/components/monitoring/__tests__/AlertRulesPanel.snapshot.test.tsx
     → Expected: 3 tests pass, no snapshot updates needed.

If all 5 steps succeed, this item is resolved.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CLOSE-05 rules panel daemon-wiring verification"
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
            f"\nOK — CLOSE-05 approved {timestamp}.\n"
            f"Evidence snippet for 04-HUMAN-UAT.md:\n\n"
            f"  **result:** resolved ({timestamp} — verified via operator run "
            f"+ Vitest snapshot test frontend/src/components/monitoring/"
            f"__tests__/AlertRulesPanel.snapshot.test.tsx) {note}\n"
        )
        return 0
    else:
        print(
            f"\nNOT OK — CLOSE-05 verification reported as: {decision!r}.\n"
            f"Paste the issue into .planning/milestones/v1.0-phases/"
            f"04-portfolio-ui-analytics-uplift/04-HUMAN-UAT.md item 2's "
            f"'issues:' section and re-run once fixed.\n"
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
