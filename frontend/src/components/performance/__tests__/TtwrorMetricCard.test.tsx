import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TtwrorMetricCard from "../TtwrorMetricCard";
import type { ReturnsResponse } from "../../../api/types";

const baseData: ReturnsResponse = {
  aggregate: {
    ttwror: 12.34,
    irr: 9.87,
    snapshot_count: 45,
    start_value: 100000,
    end_value: 112340,
    window_days: 365,
  },
  positions: [
    {
      ticker: "AAPL",
      ttwror: 15.2,
      irr: 11.3,
      hold_days: 200,
      cost_basis: 5000,
      current_value: 5760,
      status: "open",
    },
    {
      ticker: "MSFT",
      ttwror: -4.5,
      irr: null,
      hold_days: 30,
      cost_basis: 3000,
      current_value: 2865,
      status: "open",
    },
  ],
};

describe("TtwrorMetricCard", () => {
  it("renders aggregate TTWROR and IRR", () => {
    render(<TtwrorMetricCard data={baseData} loading={false} error={null} />);
    expect(screen.getByTestId("ttwror-value")).toHaveTextContent("+12.34%");
    expect(screen.getByTestId("irr-value")).toHaveTextContent("+9.87%");
  });

  it("renders '--' for null ttwror", () => {
    render(
      <TtwrorMetricCard
        data={{ ...baseData, aggregate: { ...baseData.aggregate, ttwror: null } }}
        loading={false}
        error={null}
      />,
    );
    expect(screen.getByTestId("ttwror-value")).toHaveTextContent("--");
  });

  it("shows EmptyState when snapshot_count < 2", () => {
    render(
      <TtwrorMetricCard
        data={{ ...baseData, aggregate: { ...baseData.aggregate, snapshot_count: 1 } }}
        loading={false}
        error={null}
      />,
    );
    expect(
      screen.getByText(/Need at least 2 portfolio snapshots/i),
    ).toBeInTheDocument();
  });

  it("renders per-position rows", () => {
    render(<TtwrorMetricCard data={baseData} loading={false} error={null} />);
    expect(screen.getByTestId("position-ttwror-AAPL")).toHaveTextContent("+15.20%");
    expect(screen.getByTestId("position-irr-MSFT")).toHaveTextContent("--");
  });

  it("shows SkeletonCard while loading", () => {
    const { container } = render(
      <TtwrorMetricCard data={null} loading={true} error={null} />,
    );
    expect(container.firstChild).toBeTruthy();
  });

  it("shows error message when error is provided", () => {
    render(
      <TtwrorMetricCard
        data={null}
        loading={false}
        error="Failed to load returns"
      />,
    );
    expect(screen.getByText("Failed to load returns")).toBeInTheDocument();
  });
});
