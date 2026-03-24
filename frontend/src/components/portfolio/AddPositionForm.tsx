import { useState, useEffect } from "react";
import { TextInput, SelectInput } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";

export interface AddPositionInitialValues {
  ticker?: string;
  asset_type?: string;
  avg_cost?: string;
}

interface Props {
  onAdd: (data: {
    ticker: string;
    asset_type: string;
    quantity: number;
    avg_cost: number;
    entry_date: string;
    thesis_text?: string;
    expected_return_pct?: number;
    expected_hold_days?: number;
    target_price?: number;
    stop_loss?: number;
  }) => Promise<void> | void;
  loading?: boolean;
  initialValues?: AddPositionInitialValues;
}

export default function AddPositionForm({ onAdd, loading, initialValues }: Props) {
  const [ticker, setTicker] = useState(initialValues?.ticker ?? "");
  const [assetType, setAssetType] = useState(initialValues?.asset_type ?? "stock");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState(initialValues?.avg_cost ?? "");
  const [entryDate, setEntryDate] = useState(
    new Date().toISOString().slice(0, 10),
  );

  // Pre-fill fields when initialValues changes (e.g. from query params)
  useEffect(() => {
    if (initialValues?.ticker) setTicker(initialValues.ticker);
    if (initialValues?.asset_type) setAssetType(initialValues.asset_type);
    if (initialValues?.avg_cost) setAvgCost(initialValues.avg_cost);
  }, [initialValues?.ticker, initialValues?.asset_type, initialValues?.avg_cost]);

  // Thesis fields
  const [thesisOpen, setThesisOpen] = useState(false);
  const [thesisText, setThesisText] = useState("");
  const [expectedReturn, setExpectedReturn] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [expectedHoldDays, setExpectedHoldDays] = useState("");
  const [stopLoss, setStopLoss] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker || !quantity || !avgCost) return;
    try {
      const payload: Parameters<typeof onAdd>[0] = {
        ticker: ticker.toUpperCase(),
        asset_type: assetType,
        quantity: parseFloat(quantity),
        avg_cost: parseFloat(avgCost),
        entry_date: entryDate,
      };

      // Attach thesis fields if any are filled
      if (thesisText.trim()) payload.thesis_text = thesisText.trim();
      if (expectedReturn)
        payload.expected_return_pct = parseFloat(expectedReturn) / 100;
      if (targetPrice) payload.target_price = parseFloat(targetPrice);
      if (expectedHoldDays)
        payload.expected_hold_days = parseInt(expectedHoldDays, 10);
      if (stopLoss) payload.stop_loss = parseFloat(stopLoss);

      await onAdd(payload);
      // Clear all fields on success
      setTicker("");
      setQuantity("");
      setAvgCost("");
      setThesisText("");
      setExpectedReturn("");
      setTargetPrice("");
      setExpectedHoldDays("");
      setStopLoss("");
    } catch {
      // Keep form values on failure so user doesn't lose input
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <TextInput
          label="Ticker"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="AAPL"
          className="w-24"
        />
        <SelectInput
          label="Type"
          options={[
            { value: "stock", label: "Stock" },
            { value: "btc", label: "BTC" },
            { value: "eth", label: "ETH" },
          ]}
          value={assetType}
          onChange={(e) => setAssetType(e.target.value)}
        />
        <TextInput
          label="Quantity"
          type="number"
          step="any"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          className="w-24"
        />
        <TextInput
          label="Avg Cost"
          type="number"
          step="any"
          value={avgCost}
          onChange={(e) => setAvgCost(e.target.value)}
          className="w-28"
        />
        <TextInput
          label="Entry Date"
          type="date"
          value={entryDate}
          onChange={(e) => setEntryDate(e.target.value)}
        />
        <Button type="submit" loading={loading}>
          Add Position
        </Button>
      </div>

      {/* Collapsible thesis section */}
      <div>
        <Button
          variant="ghost"
          size="sm"
          type="button"
          onClick={() => setThesisOpen(!thesisOpen)}
        >
          {thesisOpen ? "Hide thesis \u2212" : "Add thesis +"}
        </Button>

        {thesisOpen && (
          <div className="mt-3 p-4 rounded-lg border border-gray-700/50 bg-gray-800/30 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Thesis
              </label>
              <textarea
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-100 placeholder:text-gray-500 focus:ring-2 focus:ring-accent focus:border-accent outline-none"
                rows={2}
                value={thesisText}
                onChange={(e) => setThesisText(e.target.value)}
                placeholder="Why are you buying? e.g. AI growth thesis..."
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <TextInput
                label="Expected Return %"
                type="number"
                step="any"
                value={expectedReturn}
                onChange={(e) => setExpectedReturn(e.target.value)}
                placeholder="18"
                className="w-24"
              />
              <TextInput
                label="Target Price"
                type="number"
                step="any"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
                placeholder="220"
                className="w-28"
              />
              <TextInput
                label="Expected Hold Days"
                type="number"
                step="1"
                value={expectedHoldDays}
                onChange={(e) => setExpectedHoldDays(e.target.value)}
                placeholder="60"
                className="w-28"
              />
              <TextInput
                label="Stop Loss"
                type="number"
                step="any"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                placeholder="170"
                className="w-28"
              />
            </div>
          </div>
        )}
      </div>
    </form>
  );
}
