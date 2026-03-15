import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import WarningsBanner from "../WarningsBanner";

describe("WarningsBanner", () => {
  it("returns null when warnings is empty array", () => {
    const { container } = render(<WarningsBanner warnings={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders single warning as text", () => {
    render(<WarningsBanner warnings={["Something went wrong"]} />);

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    // Single warning should not render as a list item
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("renders multiple warnings as bulleted list", () => {
    const warnings = ["First warning", "Second warning", "Third warning"];
    render(<WarningsBanner warnings={warnings} />);

    const list = screen.getByRole("list");
    expect(list).toBeInTheDocument();

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("First warning");
    expect(items[1]).toHaveTextContent("Second warning");
    expect(items[2]).toHaveTextContent("Third warning");
  });

  it("shows warning icon/styling (amber colors)", () => {
    const { container } = render(
      <WarningsBanner warnings={["Caution"]} />,
    );

    // The root div should have amber-related class names
    const banner = container.firstElementChild as HTMLElement;
    expect(banner.className).toContain("amber");

    // The warning icon is rendered as ⚠ (unicode 9888 / HTML &#9888;)
    expect(screen.getByText("\u26A0")).toBeInTheDocument();
  });
});
