import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiGet, apiPost, apiPut, apiPatch, apiDelete, ApiError } from "../client";

describe("API client", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  function mockFetchOk(body: unknown, status = 200) {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status,
      json: () => Promise.resolve(body),
    });
  }

  function mockFetchError(body: unknown, status: number) {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status,
      statusText: "Bad Request",
      json: () => Promise.resolve(body),
    });
  }

  describe("apiGet", () => {
    it("returns the correct envelope on success", async () => {
      const envelope = { data: { id: 1 }, warnings: [] };
      mockFetchOk(envelope);

      const result = await apiGet("/portfolios");

      expect(result).toEqual(envelope);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/portfolios",
        expect.objectContaining({ method: "GET" }),
      );
    });

    it("sets Content-Type header to application/json", async () => {
      mockFetchOk({ data: null, warnings: [] });

      await apiGet("/test");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/test",
        expect.objectContaining({
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
  });

  describe("apiPost", () => {
    it("sends body as JSON string", async () => {
      mockFetchOk({ data: { created: true }, warnings: [] });

      const body = { name: "My Portfolio", tickers: ["AAPL"] };
      await apiPost("/portfolios", body);

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/portfolios",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(body),
        }),
      );
    });

    it("returns the envelope on success", async () => {
      const envelope = { data: { id: 2 }, warnings: ["slow"] };
      mockFetchOk(envelope);

      const result = await apiPost("/portfolios", { name: "test" });

      expect(result).toEqual(envelope);
    });
  });

  describe("error handling", () => {
    it("throws ApiError with status and code on non-OK response", async () => {
      mockFetchError(
        { error: { code: "VALIDATION_ERROR", message: "Invalid ticker" } },
        400,
      );

      await expect(apiGet("/bad")).rejects.toThrow(ApiError);

      try {
        await apiGet("/bad");
      } catch (err) {
        const apiErr = err as ApiError;
        expect(apiErr.status).toBe(400);
        expect(apiErr.code).toBe("VALIDATION_ERROR");
        expect(apiErr.message).toBe("Invalid ticker");
      }
    });

    it("falls back to UNKNOWN code when error has no code", async () => {
      mockFetchError({}, 500);

      try {
        await apiGet("/fail");
      } catch (err) {
        const apiErr = err as ApiError;
        expect(apiErr.status).toBe(500);
        expect(apiErr.code).toBe("UNKNOWN");
      }
    });

    it("includes detail when present in error response", async () => {
      mockFetchError(
        {
          error: {
            code: "RATE_LIMIT",
            message: "Too many requests",
            detail: { retryAfter: 60 },
          },
        },
        429,
      );

      try {
        await apiGet("/limited");
      } catch (err) {
        const apiErr = err as ApiError;
        expect(apiErr.detail).toEqual({ retryAfter: 60 });
      }
    });
  });

  describe("apiPut", () => {
    it("sends PUT request with body", async () => {
      mockFetchOk({ data: { updated: true }, warnings: [] });

      await apiPut("/portfolios/1", { name: "Updated" });

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/portfolios/1",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ name: "Updated" }),
        }),
      );
    });
  });

  describe("apiPatch", () => {
    it("sends PATCH request with body", async () => {
      mockFetchOk({ data: { patched: true }, warnings: [] });

      await apiPatch("/portfolios/1", { name: "Patched" });

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/portfolios/1",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ name: "Patched" }),
        }),
      );
    });
  });

  describe("apiDelete", () => {
    it("sends DELETE request without body", async () => {
      mockFetchOk({ data: null, warnings: [] });

      await apiDelete("/portfolios/1");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/portfolios/1",
        expect.objectContaining({ method: "DELETE" }),
      );

      // DELETE should not have a body
      const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0]?.[1] as RequestInit | undefined;
      expect(callArgs?.body).toBeUndefined();
    });
  });
});
