import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PnlText from "../PnlText";

describe("PnlText", () => {
  it("positive value shows green text with + sign", () => {
    render(<PnlText value={5.2} />);
    const el = screen.getByText("+5.2%");
    expect(el).toBeInTheDocument();
    expect(el.className).toContain("text-green-400");
  });

  it("negative value shows red text", () => {
    render(<PnlText value={-3.1} />);
    const el = screen.getByText("-3.1%");
    expect(el).toBeInTheDocument();
    expect(el.className).toContain("text-red-400");
  });

  it("zero shows gray text", () => {
    render(<PnlText value={0} />);
    const el = screen.getByText("0.0%");
    expect(el).toBeInTheDocument();
    expect(el.className).toContain("text-gray-400");
  });
});
