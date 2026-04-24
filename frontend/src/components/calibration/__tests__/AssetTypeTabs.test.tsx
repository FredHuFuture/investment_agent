import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AssetTypeTabs from "../AssetTypeTabs";

describe("AssetTypeTabs", () => {
  // Test T1: renders all three tabs and responds to onChange
  it("renders Stock, BTC, ETH tabs", () => {
    render(<AssetTypeTabs value="stock" onChange={vi.fn()} />);
    expect(screen.getByTestId("cal-asset-type-tab-stock")).toBeInTheDocument();
    expect(screen.getByTestId("cal-asset-type-tab-btc")).toBeInTheDocument();
    expect(screen.getByTestId("cal-asset-type-tab-eth")).toBeInTheDocument();
  });

  it("calls onChange with correct value when tab is clicked", async () => {
    const onChange = vi.fn();
    render(<AssetTypeTabs value="stock" onChange={onChange} />);
    await userEvent.click(screen.getByTestId("cal-asset-type-tab-btc"));
    expect(onChange).toHaveBeenCalledWith("btc");
    await userEvent.click(screen.getByTestId("cal-asset-type-tab-eth"));
    expect(onChange).toHaveBeenCalledWith("eth");
  });

  // Test T12: defaults to stock selected
  it("marks the currently selected tab with aria-selected=true", () => {
    render(<AssetTypeTabs value="stock" onChange={vi.fn()} />);
    expect(
      screen.getByTestId("cal-asset-type-tab-stock").getAttribute("aria-selected"),
    ).toBe("true");
    expect(
      screen.getByTestId("cal-asset-type-tab-btc").getAttribute("aria-selected"),
    ).toBe("false");
    expect(
      screen.getByTestId("cal-asset-type-tab-eth").getAttribute("aria-selected"),
    ).toBe("false");
  });

  it("updates aria-selected when different tab is selected", () => {
    render(<AssetTypeTabs value="btc" onChange={vi.fn()} />);
    expect(
      screen.getByTestId("cal-asset-type-tab-btc").getAttribute("aria-selected"),
    ).toBe("true");
    expect(
      screen.getByTestId("cal-asset-type-tab-stock").getAttribute("aria-selected"),
    ).toBe("false");
  });
});
