import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import CommandPalette from "../CommandPalette";

// jsdom does not implement scrollIntoView
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

function renderPalette(open: boolean, onClose = vi.fn()) {
  return {
    onClose,
    ...render(
      <MemoryRouter>
        <CommandPalette open={open} onClose={onClose} />
      </MemoryRouter>,
    ),
  };
}

describe("CommandPalette", () => {
  it("returns null when open is false", () => {
    const { container } = renderPalette(false);
    expect(container.innerHTML).toBe("");
  });

  it("renders search input when open is true", () => {
    renderPalette(true);

    const input = screen.getByPlaceholderText("Search pages & actions...");
    expect(input).toBeInTheDocument();
  });

  it("renders command categories ('Pages')", () => {
    renderPalette(true);

    expect(screen.getByText("Pages")).toBeInTheDocument();
  });

  it("filters commands when typing in search", async () => {
    const user = userEvent.setup();
    renderPalette(true);

    // Initially "Dashboard" should be visible
    expect(screen.getByText("Dashboard")).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Search pages & actions...");
    await user.type(input, "Portfolio");

    // "Portfolio" should still be visible
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    // "Dashboard" should be filtered out
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
  });

  it("Escape key calls onClose", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderPalette(true, onClose);

    const input = screen.getByPlaceholderText("Search pages & actions...");
    await user.click(input);
    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalled();
  });

  it("clicking backdrop calls onClose", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = renderPalette(true, onClose);

    // The backdrop is the outermost fixed div
    const backdrop = container.firstElementChild as HTMLElement;
    await user.click(backdrop);

    expect(onClose).toHaveBeenCalled();
  });

  it("ArrowDown highlights next item", async () => {
    const user = userEvent.setup();
    renderPalette(true);

    const input = screen.getByPlaceholderText("Search pages & actions...");
    await user.click(input);

    // Initially the first item (Dashboard) should be selected
    const allButtons = screen.getAllByRole("button");
    const commandButtons = allButtons.filter(
      (btn) => btn.getAttribute("data-selected") !== null,
    );
    expect(commandButtons[0]).toHaveAttribute("data-selected", "true");

    // Press ArrowDown to move selection
    await user.keyboard("{ArrowDown}");

    // Now second item should be selected, first should not
    const updatedButtons = screen.getAllByRole("button").filter(
      (btn) => btn.getAttribute("data-selected") !== null,
    );
    expect(updatedButtons[0]).toHaveAttribute("data-selected", "false");
    expect(updatedButtons[1]).toHaveAttribute("data-selected", "true");
  });
});
