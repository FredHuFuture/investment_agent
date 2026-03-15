import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import RegimeBadge from "../RegimeBadge";

describe("RegimeBadge", () => {
  it("renders 'Bull' for bull regime", () => {
    render(<RegimeBadge regime="bull" />);
    expect(screen.getByText("Bull")).toBeInTheDocument();
  });

  it("renders 'Bear' for bear regime", () => {
    render(<RegimeBadge regime="bear" />);
    expect(screen.getByText("Bear")).toBeInTheDocument();
  });

  it("renders 'High Volatility' for high_volatility regime", () => {
    render(<RegimeBadge regime="high_volatility" />);
    expect(screen.getByText("High Volatility")).toBeInTheDocument();
  });

  it("renders 'Risk Off' for risk_off regime", () => {
    render(<RegimeBadge regime="risk_off" />);
    expect(screen.getByText("Risk Off")).toBeInTheDocument();
  });

  it("uses gray fallback for unknown regime", () => {
    render(<RegimeBadge regime="unknown_regime" />);
    const badge = screen.getByText("Unknown Regime");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-gray-700");
    expect(badge.className).toContain("text-gray-300");
  });
});
