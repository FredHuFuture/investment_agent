import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SignalBadge from "../SignalBadge";

describe("SignalBadge", () => {
  it("renders 'BUY' text for buy signal", () => {
    render(<SignalBadge signal="buy" />);
    expect(screen.getByText("BUY")).toBeInTheDocument();
  });

  it("renders 'SELL' text for sell signal", () => {
    render(<SignalBadge signal="sell" />);
    expect(screen.getByText("SELL")).toBeInTheDocument();
  });

  it("renders 'HOLD' text for hold signal", () => {
    render(<SignalBadge signal="hold" />);
    expect(screen.getByText("HOLD")).toBeInTheDocument();
  });

  it("handles unknown signal gracefully with gray fallback", () => {
    render(<SignalBadge signal="unknown" />);
    const badge = screen.getByText("UNKNOWN");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("bg-gray-700");
    expect(badge.className).toContain("text-gray-300");
  });
});
