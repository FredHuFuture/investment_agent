import { useState, useEffect } from "react";
import { TextInput, SelectInput } from "../ui/Input";
import { Button } from "../ui/Button";

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

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
      <TextInput
        label="Ticker"
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder="AAPL"
        className="w-32"
      />
      <SelectInput
        label="Asset Type"
        value={assetType}
        onChange={(e) => setAssetType(e.target.value)}
        options={[
          { value: "stock", label: "Stock" },
          { value: "crypto", label: "Crypto" },
        ]}
      />
      <label className="flex items-center gap-2 text-sm text-gray-400 pb-1">
        <input
          type="checkbox"
          checked={adaptive}
          onChange={(e) => setAdaptive(e.target.checked)}
          className="rounded border-gray-700"
        />
        Adaptive Weights
      </label>
      <Button type="submit" loading={loading}>
        Analyze
      </Button>
    </form>
  );
}
