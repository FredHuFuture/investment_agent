import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BenchmarkSelector from "../BenchmarkSelector";

describe("BenchmarkSelector", () => {
  it("renders all 5 allowlist options", () => {
    const onChange = vi.fn();
    render(<BenchmarkSelector value="SPY" onChange={onChange} />);
    const select = screen.getByTestId("benchmark-selector") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      "SPY",
      "QQQ",
      "TLT",
      "GLD",
      "BTC-USD",
    ]);
  });

  it("calls onChange with the new BenchmarkSymbol", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<BenchmarkSelector value="SPY" onChange={onChange} />);
    await user.selectOptions(screen.getByTestId("benchmark-selector"), "QQQ");
    expect(onChange).toHaveBeenCalledWith("QQQ");
  });

  it("shows current value as selected", () => {
    const onChange = vi.fn();
    render(<BenchmarkSelector value="TLT" onChange={onChange} />);
    const select = screen.getByTestId("benchmark-selector") as HTMLSelectElement;
    expect(select.value).toBe("TLT");
  });

  it("renders a label for accessibility", () => {
    const onChange = vi.fn();
    render(<BenchmarkSelector value="SPY" onChange={onChange} />);
    expect(screen.getByLabelText(/benchmark/i)).toBeInTheDocument();
  });
});
