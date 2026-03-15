import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useMobile } from "../useMobile";

function createMatchMediaMock(matches: boolean) {
  const listeners: Array<(e: MediaQueryListEvent) => void> = [];
  const mql = {
    matches,
    media: "",
    onchange: null,
    addEventListener: vi.fn((_: string, handler: (e: MediaQueryListEvent) => void) =>
      listeners.push(handler),
    ),
    removeEventListener: vi.fn((_: string, handler: (e: MediaQueryListEvent) => void) => {
      const idx = listeners.indexOf(handler);
      if (idx >= 0) listeners.splice(idx, 1);
    }),
    dispatchEvent: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    trigger(newMatches: boolean) {
      mql.matches = newMatches;
      listeners.forEach((fn) =>
        fn({ matches: newMatches } as MediaQueryListEvent),
      );
    },
  };
  return mql;
}

describe("useMobile", () => {
  let mockMql: ReturnType<typeof createMatchMediaMock>;

  beforeEach(() => {
    mockMql = createMatchMediaMock(false);
    vi.stubGlobal("matchMedia", vi.fn(() => mockMql));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns true when window width is below breakpoint", () => {
    Object.defineProperty(window, "innerWidth", {
      value: 500,
      writable: true,
      configurable: true,
    });
    mockMql = createMatchMediaMock(true);
    vi.stubGlobal("matchMedia", vi.fn(() => mockMql));

    const { result } = renderHook(() => useMobile());

    expect(result.current).toBe(true);
  });

  it("returns false when window width is at or above breakpoint", () => {
    Object.defineProperty(window, "innerWidth", {
      value: 1024,
      writable: true,
      configurable: true,
    });
    mockMql = createMatchMediaMock(false);
    vi.stubGlobal("matchMedia", vi.fn(() => mockMql));

    const { result } = renderHook(() => useMobile());

    expect(result.current).toBe(false);
  });

  it("uses default breakpoint of 768 when none specified", () => {
    Object.defineProperty(window, "innerWidth", {
      value: 800,
      writable: true,
      configurable: true,
    });
    mockMql = createMatchMediaMock(false);
    vi.stubGlobal("matchMedia", vi.fn(() => mockMql));

    renderHook(() => useMobile());

    expect(window.matchMedia).toHaveBeenCalledWith("(max-width: 767px)");
  });

  it("updates when media query changes", () => {
    Object.defineProperty(window, "innerWidth", {
      value: 1024,
      writable: true,
      configurable: true,
    });
    mockMql = createMatchMediaMock(false);
    vi.stubGlobal("matchMedia", vi.fn(() => mockMql));

    const { result } = renderHook(() => useMobile());
    expect(result.current).toBe(false);

    act(() => {
      mockMql.trigger(true);
    });

    expect(result.current).toBe(true);
  });

  it("cleans up listener on unmount", () => {
    Object.defineProperty(window, "innerWidth", {
      value: 1024,
      writable: true,
      configurable: true,
    });
    mockMql = createMatchMediaMock(false);
    vi.stubGlobal("matchMedia", vi.fn(() => mockMql));

    const { unmount } = renderHook(() => useMobile());

    unmount();

    expect(mockMql.removeEventListener).toHaveBeenCalledWith(
      "change",
      expect.any(Function),
    );
  });
});
