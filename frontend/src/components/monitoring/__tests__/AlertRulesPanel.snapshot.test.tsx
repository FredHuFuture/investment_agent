// Snapshot tests lock Phase 4 visual contracts for CLOSE-04..06 UAT resolution.
// DO NOT run `vitest -u` in CI — regenerate snapshots locally only after intentional Phase 4 component changes.
/**
 * CLOSE-05: Snapshot test locking AlertRulesPanel Built-in-badge +
 * toggle + daemon-wiring contract. The snapshot locks:
 *  - hardcoded rules sorted first
 *  - Built-in badge visible on metric=hardcoded rows
 *  - delete button hidden for hardcoded rows
 *  - metric/condition/threshold cells rendered as "—" for hardcoded rules
 *  - Toggle click calls toggleAlertRule(id, newState) with exact args
 *
 * Live daemon-log verification remains a manual step
 * (scripts/verify_close_05_rules_panel.py); this test catches
 * regressions in the static UI contract that feeds the manual path.
 *
 * Regenerate: `npx vitest -u`
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { invalidateCache } from "../../../lib/cache";
import AlertRulesPanel from "../AlertRulesPanel";

const mockToggle = vi.fn();
const mockGet = vi.fn();
const mockDelete = vi.fn();
const mockCreate = vi.fn();

vi.mock("../../../api/endpoints", () => ({
  getAlertRules: () => mockGet(),
  toggleAlertRule: (id: number, enabled: boolean) => mockToggle(id, enabled),
  deleteAlertRule: (id: number) => mockDelete(id),
  createAlertRule: (body: unknown) => mockCreate(body),
}));

const MIXED_RULES = [
  {
    id: 1,
    name: "STOP_LOSS_HIT",
    metric: "hardcoded",
    condition: "eq" as const,
    threshold: 0,
    severity: "critical",
    enabled: true,
    created_at: "2026-04-21",
  },
  {
    id: 2,
    name: "TARGET_HIT",
    metric: "hardcoded",
    condition: "eq" as const,
    threshold: 0,
    severity: "info",
    enabled: true,
    created_at: "2026-04-21",
  },
  {
    id: 3,
    name: "Custom PnL watch",
    metric: "pnl_pct",
    condition: "lt" as const,
    threshold: -5,
    severity: "warning",
    enabled: false,
    created_at: "2026-04-22",
  },
];

describe("CLOSE-05: AlertRulesPanel snapshot contract", () => {
  beforeEach(() => {
    mockToggle.mockReset();
    mockGet.mockReset();
    mockDelete.mockReset();
    mockCreate.mockReset();
    // Clear in-memory cache so each test gets a fresh fetch (not stale data from prior tests)
    invalidateCache("monitoring:alertRules");
  });

  it("A: mixed rules — hardcoded sorted first, Built-in badges, hidden deletes", async () => {
    mockGet.mockResolvedValue({ data: MIXED_RULES, warnings: [] });
    const { container } = render(<AlertRulesPanel />);
    await waitFor(() => expect(mockGet).toHaveBeenCalled());
    // Wait for rules to render before snapshotting
    await waitFor(() => {
      expect(screen.getByTestId("alert-rule-toggle-1")).toBeInTheDocument();
    });
    expect(container).toMatchSnapshot();
  });

  it("B: toggle calls toggleAlertRule with exact args", async () => {
    mockGet.mockResolvedValue({ data: MIXED_RULES, warnings: [] });
    mockToggle.mockResolvedValue({
      data: { ...MIXED_RULES[0], enabled: false },
      warnings: [],
    });
    render(<AlertRulesPanel />);
    await waitFor(() =>
      expect(screen.getByTestId("alert-rule-toggle-1")).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByTestId("alert-rule-toggle-1"));
    expect(mockToggle).toHaveBeenCalledWith(1, false); // was enabled:true, new=false
    expect(mockToggle).toHaveBeenCalledTimes(1);
  });

  it("C: empty rules list renders empty state", async () => {
    mockGet.mockResolvedValue({ data: [], warnings: [] });
    const { container } = render(<AlertRulesPanel />);
    // Cache was cleared in beforeEach so mockGet will be called fresh.
    // When data is [] the component renders the EmptyState ("No alert rules configured.")
    await waitFor(() => expect(mockGet).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByText(/No alert rules configured/i)).toBeInTheDocument(),
    );
    expect(container).toMatchSnapshot();
  });
});
