import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TargetWeightBar from "../TargetWeightBar";

describe("TargetWeightBar", () => {
  it("returns null when targetWeight is null", () => {
    const { container } = render(
      <TargetWeightBar actualWeight={0.15} targetWeight={null} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows overweight amber color and positive deviation label", () => {
    render(<TargetWeightBar actualWeight={0.15} targetWeight={0.10} ticker="AAPL" />);
    const bar = screen.getByTestId("target-weight-bar-AAPL");
    expect(bar).toHaveTextContent("+5.0%");
    expect(bar.innerHTML).toMatch(/amber/i);
  });

  it("shows underweight green color and negative deviation label", () => {
    render(<TargetWeightBar actualWeight={0.05} targetWeight={0.10} ticker="MSFT" />);
    const bar = screen.getByTestId("target-weight-bar-MSFT");
    expect(bar).toHaveTextContent("-5.0%");
    expect(bar.innerHTML).toMatch(/green/i);
  });

  it("shows near-zero deviation as neutral", () => {
    render(<TargetWeightBar actualWeight={0.1001} targetWeight={0.1000} ticker="GOOG" />);
    const bar = screen.getByTestId("target-weight-bar-GOOG");
    expect(bar).toHaveTextContent("+0.0%");
  });

  it("includes target weight in tooltip text", () => {
    render(<TargetWeightBar actualWeight={0.15} targetWeight={0.10} ticker="NVDA" />);
    expect(screen.getByText(/target 10\.0%/i)).toBeInTheDocument();
  });
});
