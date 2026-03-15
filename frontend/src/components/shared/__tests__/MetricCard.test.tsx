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
    // The sub text is in a div with text-xs class; should not exist
    const subElements = container.querySelectorAll(".text-xs");
    expect(subElements.length).toBe(0);
  });

  it("applies green accent for trend='up'", () => {
    const { container } = render(
      <MetricCard label="Return" value="+10%" trend="up" />,
    );
    const card = container.firstElementChild as HTMLElement;
    expect(card.className).toContain("border-l-green-500/60");
  });

  it("applies red accent for trend='down'", () => {
    const { container } = render(
      <MetricCard label="Loss" value="-3%" trend="down" />,
    );
    const card = container.firstElementChild as HTMLElement;
    expect(card.className).toContain("border-l-red-500/60");
  });

  it("applies transparent border when no trend is set", () => {
    const { container } = render(
      <MetricCard label="Neutral" value="0%" />,
    );
    const card = container.firstElementChild as HTMLElement;
    expect(card.className).toContain("border-l-transparent");
  });

  it("applies green value color for trend='up'", () => {
    render(<MetricCard label="Up" value="+5%" trend="up" />);
    const valueEl = screen.getByText("+5%");
    expect(valueEl.className).toContain("text-green-400");
  });

  it("applies red value color for trend='down'", () => {
    render(<MetricCard label="Down" value="-5%" trend="down" />);
    const valueEl = screen.getByText("-5%");
    expect(valueEl.className).toContain("text-red-400");
  });

  it("applies white value color when no trend", () => {
    render(<MetricCard label="Neutral" value="0" />);
    const valueEl = screen.getByText("0");
    expect(valueEl.className).toContain("text-white");
  });

  it("applies sub text color matching trend='up'", () => {
    render(<MetricCard label="G" value="1" sub="rising" trend="up" />);
    const subEl = screen.getByText("rising");
    expect(subEl.className).toContain("text-green-500/70");
  });

  it("applies sub text color matching trend='down'", () => {
    render(<MetricCard label="L" value="1" sub="falling" trend="down" />);
    const subEl = screen.getByText("falling");
    expect(subEl.className).toContain("text-red-500/70");
  });

  it("overrides value color with custom className", () => {
    render(
      <MetricCard label="Custom" value="42" className="text-yellow-400" trend="up" />,
    );
    const valueEl = screen.getByText("42");
    // className prop overrides the trend-based color
    expect(valueEl.className).toContain("text-yellow-400");
  });

  it("renders with only required props (label and value)", () => {
    const { container } = render(<MetricCard label="Min" value="0" />);
    expect(container.firstElementChild).toBeInTheDocument();
    expect(screen.getByText("Min")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});
