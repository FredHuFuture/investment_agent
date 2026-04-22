import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AlertRulesPanel from "../AlertRulesPanel";

vi.mock("../../../api/endpoints", () => ({
  getAlertRules: vi.fn(() =>
    Promise.resolve({
      data: [
        {
          id: 1,
          name: "STOP_LOSS_HIT",
          metric: "hardcoded",
          condition: "eq",
          threshold: 0,
          severity: "critical",
          enabled: true,
          created_at: "2026-04-21",
        },
        {
          id: 2,
          name: "TARGET_HIT",
          metric: "hardcoded",
          condition: "eq",
          threshold: 0,
          severity: "low",
          enabled: true,
          created_at: "2026-04-21",
        },
        {
          id: 3,
          name: "My Drawdown Rule",
          metric: "drawdown_pct",
          condition: "gt",
          threshold: 10,
          severity: "high",
          enabled: true,
          created_at: "2026-04-21",
        },
      ],
      warnings: [],
    }),
  ),
  createAlertRule: vi.fn(),
  deleteAlertRule: vi.fn(),
  toggleAlertRule: vi.fn((id: number, enabled: boolean) =>
    Promise.resolve({
      data: {
        id,
        name: "STOP_LOSS_HIT",
        metric: "hardcoded",
        condition: "eq",
        threshold: 0,
        severity: "critical",
        enabled,
        created_at: "2026-04-21",
      },
      warnings: [],
    }),
  ),
}));

describe("AlertRulesPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists built-in and user rules", async () => {
    render(<AlertRulesPanel />);
    await waitFor(() => {
      expect(screen.getByText("STOP_LOSS_HIT")).toBeInTheDocument();
      expect(screen.getByText("TARGET_HIT")).toBeInTheDocument();
      expect(screen.getByText("My Drawdown Rule")).toBeInTheDocument();
    });
  });

  it("shows 'Built-in' badge for hardcoded rules", async () => {
    render(<AlertRulesPanel />);
    await waitFor(() => {
      const badges = screen.getAllByText(/Built-in/i);
      expect(badges.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("toggling a rule fires PATCH with new enabled state", async () => {
    const user = userEvent.setup();
    const mod = await import("../../../api/endpoints");
    render(<AlertRulesPanel />);
    await waitFor(() => screen.getByText("STOP_LOSS_HIT"));

    // The existing panel uses a <button> toggle (role=button) for each rule's enabled state.
    // Find all toggle buttons (the inline-flex rounded-full switch buttons).
    const toggles = screen.getAllByRole("button", { name: /disable rule|enable rule/i });
    if (toggles.length > 0) {
      await user.click(toggles[0]!);
      await waitFor(() => {
        expect(mod.toggleAlertRule).toHaveBeenCalled();
      });
    }
  });
});
