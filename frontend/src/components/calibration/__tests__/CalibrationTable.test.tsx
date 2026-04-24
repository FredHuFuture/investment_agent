import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import type { CalibrationResponse } from "../../../api/types";

// Mock recharts
vi.mock("recharts", () => ({
  LineChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "line-chart" }, children),
  Line: ({ stroke }: { stroke?: string }) =>
    React.createElement("div", { "data-testid": "sparkline-line", "data-stroke": stroke }),
  YAxis: () => null,
}));

import CalibrationTable from "../CalibrationTable";

const MOCK_CORPUS_META = {
  date_range: ["2024-01-01", "2024-12-28"] as [string, string],
  total_observations: 240,
  tickers_covered: ["AAPL", "NVDA"],
  n_agents: 5,
  survivorship_bias_warning: true,
};

function makeAgent(overrides = {}) {
  return {
    brier_score: 0.25,
    ic_5d: 0.12,
    ic_horizon: "5d",
    ic_ir: 0.8,
    sample_size: 60,
    preliminary_calibration: true,
    signal_source: "backtest_generated",
    rolling_ic: [0.1, 0.15, 0.08],
    ...overrides,
  };
}

const FULL_DATA: CalibrationResponse = {
  agents: {
    TechnicalAgent: makeAgent(),
    FundamentalAgent: makeAgent({
      brier_score: null,
      ic_5d: null,
      ic_ir: null,
      sample_size: 0,
      rolling_ic: [],
      note: "FundamentalAgent returns HOLD in backtest_mode (FOUND-04 contract)",
    }),
    MacroAgent: makeAgent(),
    SentimentAgent: makeAgent(),
    CryptoAgent: makeAgent(),
    SummaryAgent: makeAgent(),
  },
  corpus_metadata: MOCK_CORPUS_META,
  horizon: "5d",
  window_days: 60,
};

describe("CalibrationTable", () => {
  // Test C9: renders all 6 known agents
  it("renders a row for each of the 6 known agents", () => {
    render(<CalibrationTable data={FULL_DATA} />);
    expect(screen.getByTestId("cal-agent-row-TechnicalAgent")).toBeInTheDocument();
    expect(screen.getByTestId("cal-agent-row-FundamentalAgent")).toBeInTheDocument();
    expect(screen.getByTestId("cal-agent-row-MacroAgent")).toBeInTheDocument();
    expect(screen.getByTestId("cal-agent-row-SentimentAgent")).toBeInTheDocument();
    expect(screen.getByTestId("cal-agent-row-CryptoAgent")).toBeInTheDocument();
    expect(screen.getByTestId("cal-agent-row-SummaryAgent")).toBeInTheDocument();
  });

  // Test C10: empty corpus shows CTA, not table
  it("renders empty-corpus CTA when total_observations is 0", () => {
    const emptyData: CalibrationResponse = {
      ...FULL_DATA,
      corpus_metadata: {
        ...MOCK_CORPUS_META,
        total_observations: 0,
      },
    };
    const onRebuild = vi.fn();
    render(<CalibrationTable data={emptyData} onRebuildCorpus={onRebuild} />);
    expect(screen.getByTestId("cal-empty-corpus-cta")).toBeInTheDocument();
    expect(screen.queryByTestId("cal-calibration-table")).not.toBeInTheDocument();
  });

  it("calls onRebuildCorpus when rebuild button is clicked", async () => {
    const emptyData: CalibrationResponse = {
      ...FULL_DATA,
      corpus_metadata: { ...MOCK_CORPUS_META, total_observations: 0 },
    };
    const onRebuild = vi.fn();
    render(<CalibrationTable data={emptyData} onRebuildCorpus={onRebuild} />);
    const rebuildButton = screen.getByTestId("cal-rebuild-corpus-button");
    await userEvent.click(rebuildButton);
    expect(onRebuild).toHaveBeenCalledOnce();
  });

  it("shows survivorship bias warning when flagged", () => {
    render(<CalibrationTable data={FULL_DATA} />);
    expect(screen.getByText(/survivorship/i)).toBeInTheDocument();
  });
});
