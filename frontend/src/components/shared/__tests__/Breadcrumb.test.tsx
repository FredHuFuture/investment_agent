import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Breadcrumb, { type BreadcrumbItem } from "../Breadcrumb";

function renderBreadcrumb(items: BreadcrumbItem[]) {
  return render(
    <MemoryRouter>
      <Breadcrumb items={items} />
    </MemoryRouter>,
  );
}

describe("Breadcrumb", () => {
  it("renders breadcrumb items with correct labels", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Portfolio", href: "/portfolio" },
      { label: "Details" },
    ];

    renderBreadcrumb(items);

    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Details")).toBeInTheDocument();
  });

  it("renders Link for items with href (not the last item)", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Portfolio", href: "/portfolio" },
      { label: "Details" },
    ];

    renderBreadcrumb(items);

    // Items with href that are not last should render as anchor tags (Link)
    const links = screen.getAllByRole("link");
    expect(links.length).toBe(2);
    expect(links[0]).toHaveTextContent("Home");
    expect(links[1]).toHaveTextContent("Portfolio");
  });

  it("renders span (not link) for last item", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Current Page" },
    ];

    renderBreadcrumb(items);

    // The last item should not be a link even if it had an href
    const lastItemText = screen.getByText("Current Page");
    expect(lastItemText.tagName).toBe("SPAN");
    expect(lastItemText.closest("a")).toBeNull();
  });

  it("renders Home icon for item with label 'Home'", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Other" },
    ];

    renderBreadcrumb(items);

    // The Home item should contain an SVG (HomeIcon)
    const homeLink = screen.getByRole("link", { name: /Home/ });
    const svg = homeLink.querySelector("svg");
    expect(svg).not.toBeNull();
  });

  it("has aria-label='Breadcrumb' on nav element", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Page" },
    ];

    renderBreadcrumb(items);

    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(nav).toBeInTheDocument();
  });
});
