// Snapshot tests lock Phase 4 visual contracts for CLOSE-04..06 UAT resolution.
// DO NOT run `vitest -u` in CI — regenerate snapshots locally only after intentional Phase 4 component changes.
/**
 * CLOSE-06: Snapshot test locking DailyPnlHeatmap tooltip title contract.
 * Each cell's title attribute follows:
 *   - cell with pnl != null → "{date}: {sign}{formatCurrency(pnl)}"
 *   - cell with pnl === null → "{date}: --"
 *   - filler cell (outside range) → "" (falsy title, no tooltip)
 *
 * Live hover verification remains a manual step
 * (scripts/verify_close_06_heatmap_tooltip.py); this snapshot catches
 * regressions in the title format that feeds the manual path.
 *
 * Regenerate: `npx vitest -u`
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import DailyPnlHeatmap from "../DailyPnlHeatmap";

describe("CLOSE-06: DailyPnlHeatmap tooltip contract", () => {
  it("A: diverse pnl values produce correct title strings + colors", () => {
    // 5 consecutive business days (Mon–Fri), diverse values
    const data = [
      { date: "2026-04-13", pnl: 100.5 }, // Mon — small positive
      { date: "2026-04-14", pnl: 1500 }, // Tue — large positive
      { date: "2026-04-15", pnl: 0 }, // Wed — zero
      { date: "2026-04-16", pnl: -75.25 }, // Thu — small negative
      { date: "2026-04-17", pnl: -2000 }, // Fri — large negative
    ];
    const { container } = render(<DailyPnlHeatmap data={data} />);
    expect(container).toMatchSnapshot();
  });

  it("B: null pnl renders '--' title", () => {
    const data = [
      { date: "2026-04-13", pnl: 50 },
      { date: "2026-04-14", pnl: null as unknown as number }, // backend can send null
      { date: "2026-04-15", pnl: 25 },
    ];
    const { container } = render(<DailyPnlHeatmap data={data} />);
    expect(container).toMatchSnapshot();
  });

  it("C: empty data renders EmptyState (no table)", () => {
    const { container } = render(<DailyPnlHeatmap data={[]} />);
    expect(container).toMatchSnapshot();
  });
});
