/**
 * Simple in-memory cache with TTL for API responses.
 *
 * Survives route navigation (data stays in module scope).
 * Cleared on full page reload (F5).
 */

interface CacheEntry<T = unknown> {
  data: T;
  warnings: string[];
  timestamp: number;
}

const store = new Map<string, CacheEntry>();

/** Default TTL: 30 seconds */
export const DEFAULT_TTL_MS = 30_000;

/** Long TTL for rarely-changing data: 2 minutes */
export const LONG_TTL_MS = 120_000;

/** Short TTL for fast-changing data: 10 seconds */
export const SHORT_TTL_MS = 10_000;

/**
 * Get a cached entry if it exists and hasn't expired.
 * Returns the entry regardless of age if `ignoreExpiry` is true
 * (useful for stale-while-revalidate pattern).
 */
export function getCached<T>(
  key: string,
  ttlMs: number = DEFAULT_TTL_MS,
  ignoreExpiry = false,
): CacheEntry<T> | null {
  const entry = store.get(key) as CacheEntry<T> | undefined;
  if (!entry) return null;
  if (!ignoreExpiry && Date.now() - entry.timestamp > ttlMs) {
    return null;
  }
  return entry;
}

/** Store data in cache. */
export function setCache<T>(
  key: string,
  data: T,
  warnings: string[] = [],
): void {
  store.set(key, { data, warnings, timestamp: Date.now() });
}

/** Check if an entry is stale (exists but past TTL). */
export function isStale(key: string, ttlMs: number = DEFAULT_TTL_MS): boolean {
  const entry = store.get(key);
  if (!entry) return true;
  return Date.now() - entry.timestamp > ttlMs;
}

/**
 * Invalidate cache entries by prefix.
 * `invalidateCache("portfolio")` clears all keys starting with "portfolio".
 * `invalidateCache()` clears everything.
 */
export function invalidateCache(prefix?: string): void {
  if (!prefix) {
    store.clear();
    return;
  }
  for (const key of store.keys()) {
    if (key.startsWith(prefix)) {
      store.delete(key);
    }
  }
}
