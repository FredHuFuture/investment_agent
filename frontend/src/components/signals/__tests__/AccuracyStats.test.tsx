import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AccuracyStats from "../AccuracyStats";
import type { AccuracyStats as AccuracyStatsType } from "../../../api/types";

const baseData: AccuracyStatsType = {
  total_signals: 50,
  resolved_count: 18,
  win_count: 14,
  loss_count: 4,
  win_rate: 0.778, // 0-1 fraction from tracker.compute_accuracy_stats
  avg_confidence: 71.2,
  by_signal: { BUY: { count: 10, win_rate: 0.6 } },
  by_regime: { RISK_ON: { count: 8, win_rate: 1 } },
  by_asset_type: {},
};

describe("AccuracyStats win-rate scaling", () => {
  it("renders the 0-1 win_rate fraction as a percentage (×100)", () => {
    render(<AccuracyStats data={baseData} />);
    expect(screen.getByText("77.8%")).toBeInTheDocument();
    // The pre-fix bug rendered the raw fraction as "0.8%".
    expect(screen.queryByText("0.8%")).not.toBeInTheDocument();
  });

  it("scales by_signal and by_regime win rates", () => {
    render(<AccuracyStats data={baseData} />);
    expect(screen.getByText(/60\.0%/)).toBeInTheDocument(); // BUY 0.6 -> 60.0%
    expect(screen.getByText(/100\.0%/)).toBeInTheDocument(); // RISK_ON 1 -> 100.0%
  });

  it("shows N/A when overall win_rate is null", () => {
    render(<AccuracyStats data={{ ...baseData, win_rate: null }} />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
  });
});
