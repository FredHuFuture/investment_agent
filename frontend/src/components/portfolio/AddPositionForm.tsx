import { useState } from "react";

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
}

export default function AddPositionForm({ onAdd, loading }: Props) {
  const [ticker, setTicker] = useState("");
  const [assetType, setAssetType] = useState("stock");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [entryDate, setEntryDate] = useState(
    new Date().toISOString().slice(0, 10),
  );

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

  const inputCls =
    "bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 transition-colors";

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
            Ticker
          </label>
          <input
            className={`${inputCls} w-24`}
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="AAPL"
          />
        </div>
        <div>
          <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
            Type
          </label>
          <select
            className={inputCls}
            value={assetType}
            onChange={(e) => setAssetType(e.target.value)}
          >
            <option value="stock">Stock</option>
            <option value="btc">BTC</option>
            <option value="eth">ETH</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
            Quantity
          </label>
          <input
            className={`${inputCls} w-24`}
            type="number"
            step="any"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
            Avg Cost
          </label>
          <input
            className={`${inputCls} w-28`}
            type="number"
            step="any"
            value={avgCost}
            onChange={(e) => setAvgCost(e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
            Entry Date
          </label>
          <input
            className={inputCls}
            type="date"
            value={entryDate}
            onChange={(e) => setEntryDate(e.target.value)}
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors duration-150"
        >
          {loading ? "Adding..." : "Add Position"}
        </button>
      </div>

      {/* Collapsible thesis section */}
      <div>
        <button
          type="button"
          onClick={() => setThesisOpen(!thesisOpen)}
          className="text-xs text-blue-400 hover:text-blue-300 transition-colors duration-150 font-medium"
        >
          {thesisOpen ? "Hide thesis \u2212" : "Add thesis +"}
        </button>

        {thesisOpen && (
          <div className="mt-3 p-4 rounded-lg border border-gray-700/50 bg-gray-800/30 space-y-4">
            <div>
              <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
                Thesis
              </label>
              <textarea
                className={`${inputCls} w-full`}
                rows={2}
                value={thesisText}
                onChange={(e) => setThesisText(e.target.value)}
                placeholder="Why are you buying? e.g. AI growth thesis..."
              />
            </div>
            <div className="flex flex-wrap gap-3">
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
                  Expected Return %
                </label>
                <input
                  className={`${inputCls} w-24`}
                  type="number"
                  step="any"
                  value={expectedReturn}
                  onChange={(e) => setExpectedReturn(e.target.value)}
                  placeholder="18"
                />
              </div>
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
                  Target Price
                </label>
                <input
                  className={`${inputCls} w-28`}
                  type="number"
                  step="any"
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(e.target.value)}
                  placeholder="220"
                />
              </div>
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
                  Expected Hold Days
                </label>
                <input
                  className={`${inputCls} w-28`}
                  type="number"
                  step="1"
                  value={expectedHoldDays}
                  onChange={(e) => setExpectedHoldDays(e.target.value)}
                  placeholder="60"
                />
              </div>
              <div>
                <label className="block text-xs font-medium uppercase tracking-wider text-gray-500 mb-1.5">
                  Stop Loss
                </label>
                <input
                  className={`${inputCls} w-28`}
                  type="number"
                  step="any"
                  value={stopLoss}
                  onChange={(e) => setStopLoss(e.target.value)}
                  placeholder="170"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </form>
  );
}
