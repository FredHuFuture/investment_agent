import { useCallback, useEffect, useRef, useState } from "react";
import {
  getCached,
  setCache,
  isStale,
  DEFAULT_TTL_MS,
} from "../lib/cache";

interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  warnings: string[];
  refetch: () => void;
  /** True when showing cached data while fetching fresh data in background */
  stale: boolean;
  /** Timestamp (ms) of the last successful data fetch */
  lastUpdated: number | null;
}

interface UseApiOptions {
  /**
   * Cache key. When provided, enables caching:
   * - Returns cached data instantly (no loading spinner)
   * - Refetches in background if stale (stale-while-revalidate)
   * - Skips network call entirely if cache is fresh
   */
  cacheKey?: string;
  /** Cache TTL in milliseconds. Default: 30s */
  ttlMs?: number;
}

/**
 * Generic data-fetching hook with optional caching.
 *
 * Without `cacheKey`: behaves exactly as before (fetch on every mount).
 * With `cacheKey`: stale-while-revalidate pattern.
 */
export function useApi<T>(
  fetcher: () => Promise<{ data: T; warnings: string[] }>,
  depsOrOptions?: unknown[] | UseApiOptions,
  maybeOptions?: UseApiOptions,
): ApiState<T> {
  // Support both signatures:
  //   useApi(fn)
  //   useApi(fn, deps)
  //   useApi(fn, deps, options)
  //   useApi(fn, options)
  let deps: unknown[] = [];
  let options: UseApiOptions = {};

  if (Array.isArray(depsOrOptions)) {
    deps = depsOrOptions;
    options = maybeOptions ?? {};
  } else if (depsOrOptions && !Array.isArray(depsOrOptions)) {
    options = depsOrOptions as UseApiOptions;
  }

  const { cacheKey, ttlMs = DEFAULT_TTL_MS } = options;

  // Initialize from cache if available
  const cached = cacheKey ? getCached<T>(cacheKey, ttlMs, true) : null;

  const [data, setData] = useState<T | null>(cached?.data ?? null);
  const [loading, setLoading] = useState(cached?.data == null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>(
    cached?.warnings ?? [],
  );
  const [stale, setStale] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<number | null>(
    cached?.data != null ? Date.now() : null,
  );
  const [tick, setTick] = useState(0);
  const mountedRef = useRef(true);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    // If we have a cacheKey, check cache first
    if (cacheKey && tick === 0) {
      const entry = getCached<T>(cacheKey, ttlMs, true);

      if (entry) {
        // We have cached data — show it immediately
        setData(entry.data);
        setWarnings(entry.warnings);
        setError(null);

        if (!isStale(cacheKey, ttlMs)) {
          // Cache is fresh — skip network call entirely
          setLoading(false);
          setStale(false);
          return;
        }

        // Cache is stale — show cached data but refetch in background
        setLoading(false);
        setStale(true);
      }
    }

    // For explicit refetch (tick > 0) or no cache: show loading if no data
    if (!cacheKey || data == null) {
      setLoading(true);
    }
    setError(null);

    fetcher()
      .then((res) => {
        if (cancelled) return;
        setData(res.data);
        setWarnings(res.warnings);
        setStale(false);
        setLastUpdated(Date.now());
        // Update cache
        if (cacheKey) {
          setCache(cacheKey, res.data, res.warnings);
        }
      })
      .catch((err: Error) => {
        if (cancelled) return;
        // On error, keep stale data if available
        if (data == null) {
          setError(err.message);
        }
        setStale(false);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);

  return { data, loading, error, warnings, refetch, stale, lastUpdated };
}
