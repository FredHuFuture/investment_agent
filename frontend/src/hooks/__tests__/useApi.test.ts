import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useApi } from "../useApi";

// Mock the cache module so tests are isolated
vi.mock("../../lib/cache", () => ({
  getCached: vi.fn(() => null),
  setCache: vi.fn(),
  isStale: vi.fn(() => true),
  DEFAULT_TTL_MS: 30_000,
}));

describe("useApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts with loading true and data null", () => {
    const fetcher = vi.fn(
      () => new Promise<{ data: string; warnings: string[] }>(() => {}), // never resolves
    );

    const { result } = renderHook(() => useApi(fetcher));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("populates data and sets loading false on successful fetch", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      data: { id: 1, name: "test" },
      warnings: [],
    });

    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual({ id: 1, name: "test" });
    expect(result.current.error).toBeNull();
  });

  it("sets error message when fetch fails", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("Network failure"));

    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe("Network failure");
    expect(result.current.data).toBeNull();
  });

  it("refetch triggers a new fetch call", async () => {
    let callCount = 0;
    const fetcher = vi.fn().mockImplementation(() => {
      callCount++;
      return Promise.resolve({
        data: `response-${callCount}`,
        warnings: [],
      });
    });

    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toBe("response-1");
    expect(fetcher).toHaveBeenCalledTimes(1);

    act(() => {
      result.current.refetch();
    });

    await waitFor(() => {
      expect(result.current.data).toBe("response-2");
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("populates warnings from API response", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      data: "ok",
      warnings: ["Rate limit approaching", "Deprecated endpoint"],
    });

    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.warnings).toEqual([
      "Rate limit approaching",
      "Deprecated endpoint",
    ]);
  });

  it("sets lastUpdated after successful fetch", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      data: "ok",
      warnings: [],
    });

    const { result } = renderHook(() => useApi(fetcher));

    // Initially null (no cached data)
    expect(result.current.lastUpdated).toBeNull();

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.lastUpdated).toBeTypeOf("number");
    expect(result.current.lastUpdated).toBeGreaterThan(0);
  });

  it("does not set lastUpdated on failed fetch", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("fail"));

    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.lastUpdated).toBeNull();
  });

  it("stale is false after a successful fetch", async () => {
    const fetcher = vi.fn().mockResolvedValue({
      data: "fresh",
      warnings: [],
    });

    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.stale).toBe(false);
  });
});
