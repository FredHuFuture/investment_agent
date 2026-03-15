import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import EmptyState from "../EmptyState";

describe("EmptyState", () => {
  it("renders message text", () => {
    render(<EmptyState message="No items found" />);
    expect(screen.getByText("No items found")).toBeInTheDocument();
  });

  it("renders hint when provided", () => {
    render(<EmptyState message="No items found" hint="Try adjusting your filters" />);
    expect(screen.getByText("No items found")).toBeInTheDocument();
    expect(screen.getByText("Try adjusting your filters")).toBeInTheDocument();
  });

  it("does not render hint when not provided", () => {
    const { container } = render(<EmptyState message="No items found" />);
    const hintElements = container.querySelectorAll(".text-xs");
    expect(hintElements.length).toBe(0);
  });
});
