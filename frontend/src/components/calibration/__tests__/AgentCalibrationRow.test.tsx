import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { AgentCalibrationEntry, DriftLogEntry } from "../../../api/types";

// Mock recharts for sparkline rendering in jsdom
vi.mock("recharts", () => ({
  LineChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "line-chart" }, children),
  Line: ({ stroke }: { stroke?: string }) =>
    React.createElement("div", { "data-testid": "sparkline-line", "data-stroke": stroke }),
  YAxis: () => null,
}));

import AgentCalibrationRow from "../AgentCalibrationRow";

function renderRow(name: string, entry: AgentCalibrationEntry) {
  return render(
    <table>
      <tbody>
        <AgentCalibrationRow agentName={name} entry={entry} />
      </tbody>
    </table>,
  );
}

const FULL_ENTRY: AgentCalibrationEntry = {
  brier_score: 0.22,
  ic_5d: 0.15,
  ic_horizon: "5d",
  ic_ir: 0.9,
  sample_size: 60,
  preliminary_calibration: true,
  signal_source: "backtest_generated",
  rolling_ic: [0.1, 0.2, null, 0.15],
};

describe("AgentCalibrationRow", () => {
  // Test C1: renders complete row with all metrics
  it("renders Brier, IC, IC-IR and sparkline for populated entry", () => {
    renderRow("TechnicalAgent", FULL_ENTRY);
    expect(screen.getByTestId("cal-agent-row-TechnicalAgent")).toBeInTheDocument();
    expect(screen.getByText("0.220")).toBeInTheDocument();
    expect(screen.getByText("0.150")).toBeInTheDocument();
    expect(screen.getByText("0.900")).toBeInTheDocument();
    expect(screen.getByTestId("cal-ic-sparkline-TechnicalAgent")).toBeInTheDocument();
  });

  // Test C2: insufficient data shows placeholder text with threshold title
  it("shows Insufficient data text when brier and ic are null", () => {
    const insufficientEntry: AgentCalibrationEntry = {
      brier_score: null,
      ic_5d: null,
      ic_horizon: "5d",
      ic_ir: null,
      sample_size: 10,
      preliminary_calibration: true,
      signal_source: "backtest_generated",
      rolling_ic: [],
    };
    renderRow("MacroAgent", insufficientEntry);
    expect(screen.getByTestId("cal-agent-row-MacroAgent")).toBeInTheDocument();
    const insufficientCells = screen.getAllByText("Insufficient data");
    // brier, ic_5d, ic_ir are all null — at least 2 cells show the message
    expect(insufficientCells.length).toBeGreaterThanOrEqual(2);
    // Verify title attributes mention N thresholds
    const cellWithTitle = insufficientCells[0]!.closest("[title]");
    expect(cellWithTitle).not.toBeNull();
    expect(cellWithTitle!.getAttribute("title")).toMatch(/N/i);
  });

  // Test C3: FundamentalAgent note replaces metric cells
  it("renders FOUND-04 note row for FundamentalAgent with note field", () => {
    const fundEntry: AgentCalibrationEntry = {
      brier_score: null,
      ic_5d: null,
      ic_horizon: "5d",
      ic_ir: null,
      sample_size: 0,
      preliminary_calibration: true,
      signal_source: "backtest_generated",
      rolling_ic: [],
      note: "FundamentalAgent returns HOLD in backtest_mode (FOUND-04 contract)",
    };
    renderRow("FundamentalAgent", fundEntry);
    expect(screen.getByTestId("cal-agent-row-FundamentalAgent")).toBeInTheDocument();
    expect(screen.getByTestId("cal-agent-note-FundamentalAgent")).toBeInTheDocument();
    expect(
      screen.getByText(/FundamentalAgent returns HOLD/i),
    ).toBeInTheDocument();
    // Sparkline should NOT be rendered in note branch
    expect(
      screen.queryByTestId("cal-ic-sparkline-FundamentalAgent"),
    ).not.toBeInTheDocument();
  });

  // Test D1: no driftEntry prop → no drift badge (backward-compat)
  it("does not render drift badge when driftEntry is undefined", () => {
    renderRow("MacroAgent", FULL_ENTRY);
    expect(screen.queryByTestId("cal-drift-badge-MacroAgent")).toBeNull();
  });

  // Test D2: driftEntry with triggered=true → drift badge visible
  it("renders drift badge when driftEntry has triggered=true", () => {
    const driftEntry: DriftLogEntry = {
      agent_name: "MacroAgent",
      asset_type: "stock",
      evaluated_at: new Date().toISOString(),
      current_icir: 0.4,
      avg_icir_60d: 0.6,
      delta_pct: -33.0,
      threshold_type: "pct_drop",
      triggered: true,
      preliminary_threshold: false,
      weight_before: 0.2,
      weight_after: 0.13,
    };
    const { container } = render(
      <table>
        <tbody>
          <AgentCalibrationRow
            agentName="MacroAgent"
            entry={FULL_ENTRY}
            driftEntry={driftEntry}
          />
        </tbody>
      </table>,
    );
    expect(
      container.querySelector('[data-testid="cal-drift-badge-MacroAgent"]'),
    ).toBeInTheDocument();
  });

  // Test D3: FOUND-04 note branch — drift badge must NOT appear (no IC-IR cell)
  it("does not render drift badge in FOUND-04 note branch", () => {
    const noteEntry: AgentCalibrationEntry = {
      ...FULL_ENTRY,
      note: "Excluded from corpus per FOUND-04",
    };
    const driftEntry: DriftLogEntry = {
      agent_name: "FundamentalAgent",
      asset_type: "stock",
      evaluated_at: new Date().toISOString(),
      current_icir: 0.4,
      avg_icir_60d: 0.6,
      delta_pct: -33.0,
      threshold_type: "pct_drop",
      triggered: true,
      preliminary_threshold: false,
      weight_before: null,
      weight_after: null,
    };
    const { container } = render(
      <table>
        <tbody>
          <AgentCalibrationRow
            agentName="FundamentalAgent"
            entry={noteEntry}
            driftEntry={driftEntry}
          />
        </tbody>
      </table>,
    );
    expect(
      container.querySelector('[data-testid="cal-drift-badge-FundamentalAgent"]'),
    ).toBeNull();
  });
});
