import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Skeleton, SkeletonCard, SkeletonTable } from "../Skeleton";

describe("Skeleton", () => {
  it("renders with animate-pulse class", () => {
    const { container } = render(<Skeleton />);
    const el = container.firstElementChild!;
    expect(el.className).toContain("animate-pulse");
  });

  it("circular variant uses rounded-full", () => {
    const { container } = render(<Skeleton variant="circular" />);
    const el = container.firstElementChild!;
    expect(el.className).toContain("rounded-full");
    expect(el.className).toContain("animate-pulse");
  });

  it("rectangular variant uses rounded-lg", () => {
    const { container } = render(<Skeleton variant="rectangular" />);
    const el = container.firstElementChild!;
    expect(el.className).toContain("rounded-lg");
    expect(el.className).toContain("animate-pulse");
  });
});

describe("SkeletonCard", () => {
  it("renders content areas", () => {
    const { container } = render(<SkeletonCard />);
    // Should contain multiple animate-pulse skeleton elements
    const pulseElements = container.querySelectorAll(".animate-pulse");
    // At least: 1 title text line + 1 rectangular block + 3 text lines = 5
    expect(pulseElements.length).toBeGreaterThanOrEqual(5);
  });
});

describe("SkeletonTable", () => {
  it("renders correct number of rows", () => {
    const { container } = render(<SkeletonTable rows={3} columns={2} />);
    // The table has 1 header row + 3 data rows = 4 rows
    // Each row has 2 columns of skeleton elements = 2 per row
    // Total skeleton elements: (1 + 3) * 2 = 8
    const pulseElements = container.querySelectorAll(".animate-pulse");
    expect(pulseElements).toHaveLength(8);
  });
});
