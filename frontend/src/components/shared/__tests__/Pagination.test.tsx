import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Pagination from "../Pagination";

describe("Pagination", () => {
  const baseProps = {
    currentPage: 2,
    totalPages: 5,
    onPageChange: vi.fn(),
    pageSize: 10,
    totalItems: 50,
  };

  it("renders page number buttons", () => {
    render(<Pagination {...baseProps} />);

    // With 5 total pages (<=5), all page numbers 1-5 should appear
    expect(screen.getByRole("button", { name: "1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "3" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "4" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "5" })).toBeInTheDocument();
  });

  it("highlights current page button", () => {
    render(<Pagination {...baseProps} />);

    const currentBtn = screen.getByRole("button", { name: "2" });
    expect(currentBtn).toHaveAttribute("aria-current", "page");
  });

  it("calls onPageChange when clicking a page number", async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();

    render(<Pagination {...baseProps} onPageChange={onPageChange} />);

    await user.click(screen.getByRole("button", { name: "4" }));
    expect(onPageChange).toHaveBeenCalledTimes(1);
    expect(onPageChange).toHaveBeenCalledWith(4);
  });

  it("disables Previous button on first page", () => {
    render(<Pagination {...baseProps} currentPage={1} />);

    const prevBtn = screen.getByRole("button", { name: "Previous page" });
    expect(prevBtn).toBeDisabled();
  });

  it("disables Next button on last page", () => {
    render(<Pagination {...baseProps} currentPage={5} />);

    const nextBtn = screen.getByRole("button", { name: "Next page" });
    expect(nextBtn).toBeDisabled();
  });

  it("shows correct 'Showing X-Y of Z items' text", () => {
    render(
      <Pagination
        {...baseProps}
        currentPage={2}
        pageSize={10}
        totalItems={50}
      />,
    );

    expect(screen.getByText("Showing 11-20 of 50 items")).toBeInTheDocument();
  });

  it("renders page size selector when onPageSizeChange provided", () => {
    const onPageSizeChange = vi.fn();

    render(
      <Pagination
        {...baseProps}
        onPageSizeChange={onPageSizeChange}
      />,
    );

    expect(screen.getByText("Rows per page")).toBeInTheDocument();
    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();
  });

  it("computes ellipsis for many pages", () => {
    const { container } = render(
      <Pagination
        {...baseProps}
        currentPage={10}
        totalPages={20}
        totalItems={200}
      />,
    );

    // With currentPage=10, totalPages=20, there should be ellipsis gaps
    // The getPageNumbers algorithm produces: 1 ... 9 10 11 ... 20
    // Ellipsis is rendered as &hellip; (…)
    const ellipses = container.querySelectorAll("span");
    const ellipsisElements = Array.from(ellipses).filter(
      (el) => el.textContent === "\u2026",
    );
    expect(ellipsisElements.length).toBeGreaterThanOrEqual(1);
  });
});
