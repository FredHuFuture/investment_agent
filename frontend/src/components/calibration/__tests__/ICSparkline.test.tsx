import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

// Mock recharts to avoid jsdom canvas/SVG rendering issues.
vi.mock("recharts", () => ({
  LineChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "line-chart" }, children),
  Line: ({ stroke }: { stroke?: string }) =>
    React.createElement("div", { "data-testid": "sparkline-line", "data-stroke": stroke }),
  YAxis: () => null,
}));

import ICSparkline, { sparklineColor } from "../ICSparkline";

describe("ICSparkline", () => {
  // Test C4: green for ic_ir > 1.0
  it("uses green stroke for IC-IR > 1.0", () => {
    render(
      <ICSparkline agentName="TechnicalAgent" rollingIc={[0.1, 0.2, 0.15]} icIr={1.2} />,
    );
    const wrapper = screen.getByTestId("cal-ic-sparkline-TechnicalAgent");
    expect(wrapper).toBeInTheDocument();
    expect(wrapper.getAttribute("data-stroke")).toBe("#10B981");
  });

  // Test C5: amber for 0.5 <= ic_ir <= 1.0
  it("uses amber stroke for IC-IR between 0.5 and 1.0", () => {
    render(
      <ICSparkline agentName="MacroAgent" rollingIc={[0.05, 0.08, 0.06]} icIr={0.7} />,
    );
    const wrapper = screen.getByTestId("cal-ic-sparkline-MacroAgent");
    expect(wrapper.getAttribute("data-stroke")).toBe("#F59E0B");
  });

  // Test C6: red for ic_ir < 0.5
  it("uses red stroke for IC-IR < 0.5", () => {
    render(
      <ICSparkline agentName="SentimentAgent" rollingIc={[0.01, -0.02, 0.03]} icIr={0.3} />,
    );
    const wrapper = screen.getByTestId("cal-ic-sparkline-SentimentAgent");
    expect(wrapper.getAttribute("data-stroke")).toBe("#EF4444");
  });

  // Test C7: gray for ic_ir null
  it("uses gray stroke for IC-IR null", () => {
    render(
      <ICSparkline agentName="CryptoAgent" rollingIc={[0.1, 0.2]} icIr={null} />,
    );
    const wrapper = screen.getByTestId("cal-ic-sparkline-CryptoAgent");
    expect(wrapper.getAttribute("data-stroke")).toBe("#6B7280");
  });

  // Test C8: empty state when rolling_ic is empty
  it("renders empty-state span when rollingIc is empty", () => {
    render(
      <ICSparkline agentName="TechnicalAgent" rollingIc={[]} icIr={null} />,
    );
    expect(
      screen.getByTestId("cal-ic-sparkline-empty-TechnicalAgent"),
    ).toBeInTheDocument();
    expect(screen.getByText("No IC history")).toBeInTheDocument();
  });

  // sparklineColor unit tests
  it("sparklineColor returns correct colors", () => {
    expect(sparklineColor(null)).toBe("#6B7280");
    expect(sparklineColor(1.1)).toBe("#10B981");
    expect(sparklineColor(0.75)).toBe("#F59E0B");
    expect(sparklineColor(0.5)).toBe("#F59E0B");
    expect(sparklineColor(0.49)).toBe("#EF4444");
    expect(sparklineColor(-0.5)).toBe("#EF4444");
  });
});
