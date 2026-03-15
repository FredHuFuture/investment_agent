import { renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { usePageTitle } from "../usePageTitle";

describe("usePageTitle", () => {
  it("sets document.title with suffix on mount", () => {
    renderHook(() => usePageTitle("Dashboard"));

    expect(document.title).toBe("Dashboard | Investment Agent");
  });

  it("resets document.title on unmount", () => {
    const { unmount } = renderHook(() => usePageTitle("Dashboard"));

    expect(document.title).toBe("Dashboard | Investment Agent");

    unmount();

    expect(document.title).toBe("Investment Agent");
  });

  it("updates document.title when title prop changes", () => {
    const { rerender } = renderHook(({ title }) => usePageTitle(title), {
      initialProps: { title: "Dashboard" },
    });

    expect(document.title).toBe("Dashboard | Investment Agent");

    rerender({ title: "Settings" });

    expect(document.title).toBe("Settings | Investment Agent");
  });

  it('uses correct format "Title | Investment Agent"', () => {
    renderHook(() => usePageTitle("Portfolio"));

    expect(document.title).toBe("Portfolio | Investment Agent");
    expect(document.title).toContain(" | ");
    expect(document.title).toMatch(/^.+ \| Investment Agent$/);
  });
});
