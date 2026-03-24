import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MetricCard from "../MetricCard";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Total Return" value="$12,345" />);
    expect(screen.getByText("Total Return")).toBeInTheDocument();
    expect(screen.getByText("$12,345")).toBeInTheDocument();
  });

  it("shows sub text when provided", () => {
    render(<MetricCard label="Gain" value="+5.2%" sub="vs. benchmark" />);
    expect(screen.getByText("vs. benchmark")).toBeInTheDocument();
  });

  it("does not render sub element when sub is not provided", () => {
    const { container } = render(<MetricCard label="Price" value="$100" />);
    const subElements = container.querySelectorAll(".text-xs");
    expect(subElements.length).toBe(0);
  });

  it("applies up value color for trend='up'", () => {
    render(<MetricCard label="Up" value="+5%" trend="up" />);
    const valueEl = screen.getByText("+5%");
    expect(valueEl.className).toContain("text-up");
  });

  it("applies down value color for trend='down'", () => {
    render(<MetricCard label="Down" value="-5%" trend="down" />);
    const valueEl = screen.getByText("-5%");
    expect(valueEl.className).toContain("text-down");
  });

  it("applies neutral value color when no trend", () => {
    render(<MetricCard label="Neutral" value="0" />);
    const valueEl = screen.getByText("0");
    expect(valueEl.className).toContain("text-gray-100");
  });

  it("applies sub text color matching trend='up'", () => {
    render(<MetricCard label="G" value="1" sub="rising" trend="up" />);
    const subEl = screen.getByText("rising");
    expect(subEl.className).toContain("text-up/70");
  });

  it("applies sub text color matching trend='down'", () => {
    render(<MetricCard label="L" value="1" sub="falling" trend="down" />);
    const subEl = screen.getByText("falling");
    expect(subEl.className).toContain("text-down/70");
  });

  it("overrides value color with custom className", () => {
    render(
      <MetricCard label="Custom" value="42" className="text-yellow-400" trend="up" />,
    );
    const valueEl = screen.getByText("42");
    expect(valueEl.className).toContain("text-yellow-400");
  });

  it("renders with only required props (label and value)", () => {
    const { container } = render(<MetricCard label="Min" value="0" />);
    expect(container.firstElementChild).toBeInTheDocument();
    expect(screen.getByText("Min")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("uses display font for value", () => {
    render(<MetricCard label="Val" value="$100" />);
    const valueEl = screen.getByText("$100");
    expect(valueEl.className).toContain("font-display");
  });
});
