import type { BacktestMetrics } from "../api/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface SavedBacktestRun {
  id: string;
  ticker: string;
  label: string;
  params: {
    start_date: string;
    end_date: string;
    agents?: string[];
  };
  metrics: BacktestMetrics;
  equity_curve: Array<{ date: string; equity: number }>;
  saved_at: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const STORAGE_KEY = "investment_agent:backtest_history";
const MAX_RUNS = 20;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

function readStore(): SavedBacktestRun[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as SavedBacktestRun[];
  } catch {
    return [];
  }
}

function writeStore(runs: SavedBacktestRun[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(runs));
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/** Save a backtest run. Keeps max 20 entries, deleting the oldest when exceeded. */
export function saveBacktestRun(
  run: Omit<SavedBacktestRun, "id" | "saved_at">,
  label?: string,
): SavedBacktestRun {
  const runs = readStore();

  const saved: SavedBacktestRun = {
    ...run,
    label: label ?? run.label ?? "Untitled",
    id: generateId(),
    saved_at: new Date().toISOString(),
  };

  runs.push(saved);

  // Enforce max capacity - remove oldest first
  while (runs.length > MAX_RUNS) {
    runs.shift();
  }

  writeStore(runs);
  return saved;
}

/** List all saved backtest runs (newest first). */
export function listBacktestRuns(): SavedBacktestRun[] {
  return readStore().slice().reverse();
}

/** Delete a single saved run by id. */
export function deleteBacktestRun(id: string): void {
  const runs = readStore().filter((r) => r.id !== id);
  writeStore(runs);
}

/** Delete all saved runs. */
export function clearAllBacktestRuns(): void {
  localStorage.removeItem(STORAGE_KEY);
}
