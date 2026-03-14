import { useState, useEffect } from "react";

interface Props {
  onAnalyze: (ticker: string, assetType: string, adaptiveWeights: boolean) => void;
  loading?: boolean;
  initialTicker?: string;
  initialAssetType?: string;
}

export default function AnalyzeForm({
  onAnalyze,
  loading,
  initialTicker = "",
  initialAssetType = "stock",
}: Props) {
  const [ticker, setTicker] = useState(initialTicker);
  const [assetType, setAssetType] = useState(initialAssetType);
  const [adaptive, setAdaptive] = useState(false);

  // Sync with parent-provided initial ticker
  useEffect(() => {
    if (initialTicker && !ticker) {
      setTicker(initialTicker);
    }
  }, [initialTicker]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (initialAssetType) {
      setAssetType(initialAssetType);
    }
  }, [initialAssetType]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker.trim()) return;
    onAnalyze(ticker.trim().toUpperCase(), assetType, adaptive);
  }

  const inputCls =
    "bg-gray-800/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500/50";

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
      <div>
        <label className="block text-xs text-gray-500 mb-1.5">Ticker</label>
        <input
          className={`${inputCls} w-32`}
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="AAPL"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1.5">Asset Type</label>
        <select
          className={inputCls}
          value={assetType}
          onChange={(e) => setAssetType(e.target.value)}
        >
          <option value="stock">Stock</option>
          <option value="crypto">Crypto</option>
        </select>
      </div>
      <label className="flex items-center gap-2 text-sm text-gray-400 pb-1">
        <input
          type="checkbox"
          checked={adaptive}
          onChange={(e) => setAdaptive(e.target.checked)}
          className="rounded border-gray-700"
        />
        Adaptive Weights
      </label>
      <button
        type="submit"
        disabled={loading}
        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg px-5 py-2 text-sm font-medium transition-colors duration-150"
      >
        {loading ? "Analyzing..." : "Analyze"}
      </button>
    </form>
  );
}
