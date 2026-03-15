import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import TableSearch from "../TableSearch";

describe("TableSearch", () => {
  it("renders search input with placeholder", () => {
    render(<TableSearch value="" onChange={vi.fn()} placeholder="Find items..." />);

    const input = screen.getByPlaceholderText("Find items...");
    expect(input).toBeInTheDocument();
  });

  describe("with fake timers", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("typing calls onChange after debounce", () => {
      const onChange = vi.fn();

      render(<TableSearch value="" onChange={onChange} debounceMs={300} />);

      const input = screen.getByPlaceholderText("Search...");

      // Use fireEvent to avoid userEvent timer conflicts
      fireEvent.change(input, { target: { value: "test" } });

      // Before debounce fires, onChange should not have been called
      expect(onChange).not.toHaveBeenCalledWith("test");

      // Advance timers past debounce
      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(onChange).toHaveBeenCalledWith("test");
    });

    it("clear button appears when input has text", () => {
      render(<TableSearch value="" onChange={vi.fn()} />);

      // Initially no clear button
      expect(screen.queryByRole("button", { name: "Clear search" })).not.toBeInTheDocument();

      // Type some text via fireEvent
      const input = screen.getByPlaceholderText("Search...");
      fireEvent.change(input, { target: { value: "hello" } });

      // Clear button should now appear
      expect(screen.getByRole("button", { name: "Clear search" })).toBeInTheDocument();
    });

    it("clear button calls onChange with empty string", () => {
      const onChange = vi.fn();

      render(<TableSearch value="" onChange={onChange} />);

      // Type text first so clear button appears
      const input = screen.getByPlaceholderText("Search...");
      fireEvent.change(input, { target: { value: "hello" } });

      // Click clear button
      const clearBtn = screen.getByRole("button", { name: "Clear search" });
      fireEvent.click(clearBtn);

      expect(onChange).toHaveBeenCalledWith("");
    });
  });

  it("has role='search' attribute", () => {
    render(<TableSearch value="" onChange={vi.fn()} />);

    const searchContainer = screen.getByRole("search");
    expect(searchContainer).toBeInTheDocument();
  });

  it("renders magnifying glass icon", () => {
    const { container } = render(<TableSearch value="" onChange={vi.fn()} />);

    // The magnifying glass is an SVG with a circle element
    const svgs = container.querySelectorAll("svg");
    const magnifyingGlass = Array.from(svgs).find((svg) =>
      svg.querySelector("circle"),
    );
    expect(magnifyingGlass).not.toBeUndefined();
  });
});
