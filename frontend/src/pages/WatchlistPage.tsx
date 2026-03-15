import { useEffect, useState, useCallback } from "react";
import {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  analyzeWatchlistTicker,
  analyzeAllWatchlist,
} from "../api/endpoints";
import type { WatchlistItem } from "../api/types";
import SignalBadge from "../components/shared/SignalBadge";
import { usePageTitle } from "../hooks/usePageTitle";

export default function WatchlistPage() {
  usePageTitle("Watchlist");
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Add form state
  const [ticker, setTicker] = useState("");
  const [assetType, setAssetType] = useState("stock");
  const [notes, setNotes] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [adding, setAdding] = useState(false);

  // Analyzing state
  const [analyzingTicker, setAnalyzingTicker] = useState<string | null>(null);
  const [analyzingAll, setAnalyzingAll] = useState(false);
  const [batchResult, setBatchResult] = useState<{
    total: number;
    success_count: number;
  } | null>(null);

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await getWatchlist();
      setItems(res.data);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker.trim()) return;
    setAdding(true);
    try {
      await addToWatchlist({
        ticker: ticker.trim().toUpperCase(),
        asset_type: assetType,
        notes,
        target_buy_price: targetPrice ? parseFloat(targetPrice) : undefined,
      });
      setTicker("");
      setNotes("");
      setTargetPrice("");
      await fetchWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add ticker");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(t: string) {
    try {
      await removeFromWatchlist(t);
      await fetchWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove ticker");
    }
  }

  async function handleAnalyze(t: string) {
    setAnalyzingTicker(t);
    try {
      await analyzeWatchlistTicker(t);
      await fetchWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzingTicker(null);
    }
  }

  async function handleAnalyzeAll() {
    setAnalyzingAll(true);
    setBatchResult(null);
    try {
      const res = await analyzeAllWatchlist();
      setBatchResult({
        total: res.data.total,
        success_count: res.data.success_count,
      });
      await fetchWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Batch analysis failed");
    } finally {
      setAnalyzingAll(false);
    }
  }

  function relativeTime(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Watchlist</h1>

      {/* Add Form */}
      <form
        onSubmit={handleAdd}
        className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5"
      >
        <h2 className="text-sm font-semibold text-gray-300 mb-3">
          Add Ticker
        </h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Ticker</label>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="AAPL"
              className="px-3 py-1.5 bg-gray-950/60 border border-gray-800/40 rounded-lg text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500/50 w-28"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Type</label>
            <select
              value={assetType}
              onChange={(e) => setAssetType(e.target.value)}
              className="px-3 py-1.5 bg-gray-950/60 border border-gray-800/40 rounded-lg text-xs text-gray-300 focus:outline-none focus:border-blue-500/50"
            >
              <option value="stock">Stock</option>
              <option value="btc">BTC</option>
              <option value="eth">ETH</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">
              Target Price
            </label>
            <input
              type="number"
              step="0.01"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
              placeholder="Optional"
              className="px-3 py-1.5 bg-gray-950/60 border border-gray-800/40 rounded-lg text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500/50 w-28"
            />
          </div>
          <div className="flex-1 min-w-[120px]">
            <label className="block text-xs text-gray-500 mb-1">Notes</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Why you're watching..."
              className="w-full px-3 py-1.5 bg-gray-950/60 border border-gray-800/40 rounded-lg text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <button
            type="submit"
            disabled={adding || !ticker.trim()}
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-xs font-medium text-white transition-colors"
          >
            {adding ? "Adding..." : "Add"}
          </button>
        </div>
      </form>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-400/10 border border-red-400/30 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Analyze All + Batch Result */}
      {items.length > 0 && (
        <div className="flex items-center gap-4">
          <button
            onClick={handleAnalyzeAll}
            disabled={analyzingAll}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white transition-colors"
          >
            {analyzingAll ? "Analyzing All..." : "Analyze All"}
          </button>
          {batchResult && (
            <span className="text-sm text-gray-400">
              Completed: {batchResult.success_count}/{batchResult.total}{" "}
              succeeded
            </span>
          )}
        </div>
      )}

      {/* Watchlist Table */}
      <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            Loading watchlist...
          </div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            No tickers on your watchlist yet. Add one above.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800/50 text-xs text-gray-500 uppercase tracking-wider">
                <th className="text-left px-4 py-3">Ticker</th>
                <th className="text-left px-4 py-3">Type</th>
                <th className="text-left px-4 py-3">Target Price</th>
                <th className="text-left px-4 py-3">Notes</th>
                <th className="text-center px-4 py-3">Signal</th>
                <th className="text-center px-4 py-3">Confidence</th>
                <th className="text-right px-4 py-3">Last Analyzed</th>
                <th className="text-right px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors"
                >
                  <td className="px-4 py-3 font-mono font-bold text-white">
                    {item.ticker}
                  </td>
                  <td className="px-4 py-3 text-gray-400">{item.asset_type}</td>
                  <td className="px-4 py-3 text-gray-300">
                    {item.target_buy_price != null
                      ? `$${item.target_buy_price.toFixed(2)}`
                      : "-"}
                  </td>
                  <td className="px-4 py-3 text-gray-400 max-w-[200px] truncate">
                    {item.notes || "-"}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {item.last_signal ? (
                      <SignalBadge signal={item.last_signal} />
                    ) : (
                      <span className="text-gray-600">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center text-gray-300">
                    {item.last_confidence != null
                      ? `${item.last_confidence.toFixed(1)}%`
                      : "-"}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-500 text-xs">
                    {item.last_analysis_at
                      ? relativeTime(item.last_analysis_at)
                      : "Never"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleAnalyze(item.ticker)}
                        disabled={analyzingTicker === item.ticker}
                        className="px-2.5 py-1 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded text-xs font-medium transition-colors disabled:opacity-50"
                      >
                        {analyzingTicker === item.ticker
                          ? "Analyzing..."
                          : "Analyze"}
                      </button>
                      <button
                        onClick={() => handleRemove(item.ticker)}
                        className="px-2.5 py-1 bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded text-xs font-medium transition-colors"
                      >
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
