import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ConfidenceBar from "../ConfidenceBar";

describe("ConfidenceBar", () => {
  it("renders percentage text for a given value", () => {
    render(<ConfidenceBar value={0.75} />);
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("uses green color for values >= 70%", () => {
    const { container } = render(<ConfidenceBar value={0.85} />);
    const bar = container.querySelector("[style]") as HTMLElement;
    expect(bar.className).toContain("bg-green-400");
  });

  it("uses yellow color for values >= 40% and < 70%", () => {
    const { container } = render(<ConfidenceBar value={0.5} />);
    const bar = container.querySelector("[style]") as HTMLElement;
    expect(bar.className).toContain("bg-yellow-400");
  });

  it("uses red color for values < 40%", () => {
    const { container } = render(<ConfidenceBar value={0.2} />);
    const bar = container.querySelector("[style]") as HTMLElement;
    expect(bar.className).toContain("bg-red-400");
  });

  it("clamps value to 0-100 range", () => {
    const { rerender } = render(<ConfidenceBar value={1.5} />);
    expect(screen.getByText("100%")).toBeInTheDocument();

    rerender(<ConfidenceBar value={-0.5} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });
});
