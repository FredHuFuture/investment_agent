import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getCached,
  setCache,
  isStale,
  invalidateCache,
  DEFAULT_TTL_MS,
  LONG_TTL_MS,
  SHORT_TTL_MS,
} from "../cache";

describe("cache", () => {
  beforeEach(() => {
    // Start each test with a clean cache
    invalidateCache();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("TTL constants", () => {
    it("exports expected TTL values", () => {
      expect(DEFAULT_TTL_MS).toBe(30_000);
      expect(LONG_TTL_MS).toBe(120_000);
      expect(SHORT_TTL_MS).toBe(10_000);
    });
  });

  describe("setCache / getCached", () => {
    it("stores and retrieves data", () => {
      setCache("key1", { price: 100 });
      const entry = getCached<{ price: number }>("key1");
      expect(entry).not.toBeNull();
      expect(entry!.data).toEqual({ price: 100 });
    });

    it("stores warnings alongside data", () => {
      setCache("key2", "value", ["stale quote"]);
      const entry = getCached<string>("key2");
      expect(entry!.warnings).toEqual(["stale quote"]);
    });

    it("defaults warnings to empty array", () => {
      setCache("key3", 42);
      const entry = getCached<number>("key3");
      expect(entry!.warnings).toEqual([]);
    });

    it("returns null for a missing key", () => {
      expect(getCached("nonexistent")).toBeNull();
    });

    it("records a timestamp on set", () => {
      const before = Date.now();
      setCache("ts-key", "data");
      const entry = getCached<string>("ts-key");
      expect(entry!.timestamp).toBeGreaterThanOrEqual(before);
      expect(entry!.timestamp).toBeLessThanOrEqual(Date.now());
    });
  });

  describe("TTL expiration", () => {
    it("returns entry within TTL window", () => {
      setCache("fresh", "value");
      expect(getCached("fresh", DEFAULT_TTL_MS)).not.toBeNull();
    });

    it("returns null after TTL expires", () => {
      setCache("expire-me", "value");

      // Advance time past the default TTL
      vi.spyOn(Date, "now").mockReturnValue(Date.now() + DEFAULT_TTL_MS + 1);

      expect(getCached("expire-me", DEFAULT_TTL_MS)).toBeNull();
    });

    it("returns entry past TTL when ignoreExpiry is true", () => {
      setCache("stale-ok", "value");

      vi.spyOn(Date, "now").mockReturnValue(Date.now() + DEFAULT_TTL_MS + 1);

      const entry = getCached("stale-ok", DEFAULT_TTL_MS, true);
      expect(entry).not.toBeNull();
      expect(entry!.data).toBe("value");
    });

    it("uses custom TTL correctly", () => {
      setCache("short-lived", "value");

      vi.spyOn(Date, "now").mockReturnValue(Date.now() + SHORT_TTL_MS + 1);

      expect(getCached("short-lived", SHORT_TTL_MS)).toBeNull();
      // But still valid under default TTL
      vi.restoreAllMocks();
      setCache("short-lived-2", "value");
      vi.spyOn(Date, "now").mockReturnValue(Date.now() + SHORT_TTL_MS + 1);
      expect(getCached("short-lived-2", DEFAULT_TTL_MS)).not.toBeNull();
    });
  });

  describe("isStale", () => {
    it("returns true for missing keys", () => {
      expect(isStale("no-such-key")).toBe(true);
    });

    it("returns false for fresh entries", () => {
      setCache("fresh-check", "data");
      expect(isStale("fresh-check")).toBe(false);
    });

    it("returns true for expired entries", () => {
      setCache("stale-check", "data");
      vi.spyOn(Date, "now").mockReturnValue(Date.now() + DEFAULT_TTL_MS + 1);
      expect(isStale("stale-check")).toBe(true);
    });

    it("respects custom TTL parameter", () => {
      setCache("custom-ttl", "data");
      vi.spyOn(Date, "now").mockReturnValue(Date.now() + SHORT_TTL_MS + 1);
      expect(isStale("custom-ttl", SHORT_TTL_MS)).toBe(true);
      expect(isStale("custom-ttl", LONG_TTL_MS)).toBe(false);
    });
  });

  describe("invalidateCache", () => {
    it("clears all entries when called without prefix", () => {
      setCache("a", 1);
      setCache("b", 2);
      setCache("c", 3);
      invalidateCache();
      expect(getCached("a")).toBeNull();
      expect(getCached("b")).toBeNull();
      expect(getCached("c")).toBeNull();
    });

    it("clears only entries matching prefix", () => {
      setCache("portfolio:list", []);
      setCache("portfolio:detail:1", {});
      setCache("watchlist:items", []);
      invalidateCache("portfolio");
      expect(getCached("portfolio:list")).toBeNull();
      expect(getCached("portfolio:detail:1")).toBeNull();
      expect(getCached("watchlist:items")).not.toBeNull();
    });

    it("does nothing when prefix matches no keys", () => {
      setCache("keep", "me");
      invalidateCache("nonexistent-prefix");
      expect(getCached("keep")).not.toBeNull();
    });
  });
});
