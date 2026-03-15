// ---------------------------------------------------------------------------
// Backtest Presets — save / load parameter templates (localStorage)
// ---------------------------------------------------------------------------

export interface BacktestPreset {
  name: string;
  ticker: string;
  startDate: string;
  endDate: string;
  assetType: string;
  capital: string;
  frequency: string;
  posSize: string;
  stopLoss: string;
  takeProfit: string;
  buyThreshold: string;
  sellThreshold: string;
}

// ---------------------------------------------------------------------------
// Built-in presets (cannot be deleted by the user)
// ---------------------------------------------------------------------------
const BUILT_IN: BacktestPreset[] = [
  {
    name: "Conservative",
    ticker: "AAPL",
    startDate: "2023-01-01",
    endDate: "2025-12-31",
    assetType: "stock",
    capital: "100000",
    frequency: "weekly",
    posSize: "5",
    stopLoss: "5",
    takeProfit: "10",
    buyThreshold: "0.40",
    sellThreshold: "-0.40",
  },
  {
    name: "Moderate",
    ticker: "AAPL",
    startDate: "2023-01-01",
    endDate: "2025-12-31",
    assetType: "stock",
    capital: "100000",
    frequency: "weekly",
    posSize: "10",
    stopLoss: "10",
    takeProfit: "20",
    buyThreshold: "0.30",
    sellThreshold: "-0.30",
  },
  {
    name: "Aggressive",
    ticker: "BTC",
    startDate: "2023-01-01",
    endDate: "2025-12-31",
    assetType: "btc",
    capital: "100000",
    frequency: "daily",
    posSize: "20",
    stopLoss: "15",
    takeProfit: "30",
    buyThreshold: "0.20",
    sellThreshold: "-0.20",
  },
];

const STORAGE_KEY = "backtest_presets";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function readCustom(): BacktestPreset[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as BacktestPreset[];
  } catch {
    return [];
  }
}

function writeCustom(presets: BacktestPreset[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/** Return the three immutable built-in presets. */
export function getBuiltInPresets(): BacktestPreset[] {
  return BUILT_IN;
}

/** Return all presets: built-in first, then user-created. */
export function getPresets(): BacktestPreset[] {
  return [...BUILT_IN, ...readCustom()];
}

/** Save a user-created preset. Overwrites if a custom preset with the same name exists. */
export function savePreset(preset: BacktestPreset): void {
  const custom = readCustom().filter((p) => p.name !== preset.name);
  custom.push(preset);
  writeCustom(custom);
}

/** Delete a user-created preset by name. Built-in presets are silently ignored. */
export function deletePreset(name: string): void {
  const builtInNames = new Set(BUILT_IN.map((p) => p.name));
  if (builtInNames.has(name)) return;
  writeCustom(readCustom().filter((p) => p.name !== name));
}
