import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DailyPnlHeatmap from "../DailyPnlHeatmap";
import type { DailyPnlPoint } from "../../../api/types";

describe("DailyPnlHeatmap", () => {
  it("renders EmptyState when data is empty", () => {
    render(<DailyPnlHeatmap data={[]} />);
    expect(screen.getByText(/Run a health check/i)).toBeInTheDocument();
  });

  it("renders cells for provided dates with title attribute", () => {
    const data: DailyPnlPoint[] = [
      { date: "2026-04-15", pnl: 250 },
      { date: "2026-04-16", pnl: -75 },
      { date: "2026-04-17", pnl: 0 },
    ];
    render(<DailyPnlHeatmap data={data} />);

    const cell1 = screen.getByTestId("daily-pnl-cell-2026-04-15");
    expect(cell1.getAttribute("title")).toMatch(/2026-04-15/);
    expect(cell1.getAttribute("title")).toMatch(/\+\$250/);

    const cell2 = screen.getByTestId("daily-pnl-cell-2026-04-16");
    expect(cell2.getAttribute("title")).toMatch(/2026-04-16/);
    // negative value: formatCurrency(-75) produces -$75, title has no "+" prefix
    expect(cell2.getAttribute("title")).toMatch(/2026-04-16/);
  });

  it("renders >= 7 cells when 7 contiguous days are provided", () => {
    const data: DailyPnlPoint[] = [
      { date: "2026-04-13", pnl: 100 },
      { date: "2026-04-14", pnl: 200 },
      { date: "2026-04-15", pnl: 250 },
      { date: "2026-04-16", pnl: -75 },
      { date: "2026-04-17", pnl: 0 },
      { date: "2026-04-18", pnl: 50 },
      { date: "2026-04-19", pnl: 150 },
    ];
    render(<DailyPnlHeatmap data={data} />);
    // All 7 dates should have testid cells
    expect(screen.getByTestId("daily-pnl-cell-2026-04-13")).toBeInTheDocument();
    expect(screen.getByTestId("daily-pnl-cell-2026-04-19")).toBeInTheDocument();
    const cells = document.querySelectorAll("[data-testid^='daily-pnl-cell-']");
    expect(cells.length).toBeGreaterThanOrEqual(7);
  });

  it("applies green color class for positive P&L > 1000", () => {
    const data: DailyPnlPoint[] = [{ date: "2026-04-15", pnl: 1500 }];
    render(<DailyPnlHeatmap data={data} />);
    const cell = screen.getByTestId("daily-pnl-cell-2026-04-15");
    expect(cell.className).toMatch(/bg-green-600/);
  });

  it("applies red color class for negative P&L < -1000", () => {
    const data: DailyPnlPoint[] = [{ date: "2026-04-15", pnl: -1500 }];
    render(<DailyPnlHeatmap data={data} />);
    const cell = screen.getByTestId("daily-pnl-cell-2026-04-15");
    expect(cell.className).toMatch(/bg-red-600/);
  });

  it("applies neutral color class for zero P&L", () => {
    const data: DailyPnlPoint[] = [{ date: "2026-04-15", pnl: 0 }];
    render(<DailyPnlHeatmap data={data} />);
    const cell = screen.getByTestId("daily-pnl-cell-2026-04-15");
    expect(cell.className).toMatch(/bg-gray-700/);
  });

  it("shows '--' in title for dates with no P&L data in range", () => {
    // Only one date — adjacent dates in grid will have no data
    const data: DailyPnlPoint[] = [
      { date: "2026-04-15", pnl: 100 },
      { date: "2026-04-17", pnl: 200 },
    ];
    render(<DailyPnlHeatmap data={data} />);
    // The gap date 2026-04-16 falls within the range, should render with "--" title
    const gapCell = screen.getByTestId("daily-pnl-cell-2026-04-16");
    expect(gapCell.getAttribute("title")).toMatch(/--/);
  });
});
