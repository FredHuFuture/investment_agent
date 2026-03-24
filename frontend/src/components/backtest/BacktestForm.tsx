import { useState, useEffect } from "react";
import type { BacktestPreset } from "../../lib/backtestPresets";

interface Props {
  onSubmit: (params: {
    ticker: string;
    start_date: string;
    end_date: string;
    asset_type: string;
    initial_capital: number;
    rebalance_frequency: string;
    position_size_pct: number;
    stop_loss_pct: number | null;
    take_profit_pct: number | null;
    buy_threshold: number;
    sell_threshold: number;
  }) => void;
  loading?: boolean;
  presetValues?: BacktestPreset | null;
  presetKey?: number;
}

export default function BacktestForm({ onSubmit, loading, presetValues, presetKey }: Props) {
  const [ticker, setTicker] = useState("AAPL");
  const [startDate, setStartDate] = useState("2023-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [assetType, setAssetType] = useState("stock");
  const [capital, setCapital] = useState("100000");
  const [frequency, setFrequency] = useState("weekly");
  const [posSize, setPosSize] = useState("10");
  const [stopLoss, setStopLoss] = useState("10");
  const [takeProfit, setTakeProfit] = useState("20");
  const [buyThreshold, setBuyThreshold] = useState("0.30");
  const [sellThreshold, setSellThreshold] = useState("-0.30");

  // Apply preset values when presetKey changes (a new preset was loaded)
  useEffect(() => {
    if (presetValues) {
      setTicker(presetValues.ticker);
      setStartDate(presetValues.startDate);
      setEndDate(presetValues.endDate);
      setAssetType(presetValues.assetType);
      setCapital(presetValues.capital);
      setFrequency(presetValues.frequency);
      setPosSize(presetValues.posSize);
      setStopLoss(presetValues.stopLoss);
      setTakeProfit(presetValues.takeProfit);
      setBuyThreshold(presetValues.buyThreshold);
      setSellThreshold(presetValues.sellThreshold);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presetKey]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      ticker: ticker.toUpperCase(),
      start_date: startDate,
      end_date: endDate,
      asset_type: assetType,
      initial_capital: parseFloat(capital),
      rebalance_frequency: frequency,
      position_size_pct: parseFloat(posSize) / 100,
      stop_loss_pct: stopLoss ? parseFloat(stopLoss) / 100 : null,
      take_profit_pct: takeProfit ? parseFloat(takeProfit) / 100 : null,
      buy_threshold: parseFloat(buyThreshold),
      sell_threshold: parseFloat(sellThreshold),
    });
  }

  const inputCls =
    "bg-gray-800/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-accent/50 focus:border-accent/50";

  const labelCls = "block text-xs text-gray-500 mb-1.5";

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Row 1: Ticker, Type, Dates */}
      <div className="flex flex-wrap gap-3">
        <div>
          <label className={labelCls}>Ticker</label>
          <input className={`${inputCls} w-24`} value={ticker} onChange={(e) => setTicker(e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Type</label>
          <select className={inputCls} value={assetType} onChange={(e) => setAssetType(e.target.value)}>
            <option value="stock">Stock</option>
            <option value="btc">BTC</option>
            <option value="eth">ETH</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>Start</label>
          <input className={inputCls} type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>End</label>
          <input className={inputCls} type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>
      </div>

      {/* Row 2: Capital, Frequency, Position sizing */}
      <div className="flex flex-wrap gap-3">
        <div>
          <label className={labelCls}>Capital</label>
          <input className={`${inputCls} w-28`} type="number" value={capital} onChange={(e) => setCapital(e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Frequency</label>
          <select className={inputCls} value={frequency} onChange={(e) => setFrequency(e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>Pos Size %</label>
          <input className={`${inputCls} w-20`} type="number" value={posSize} onChange={(e) => setPosSize(e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Stop Loss %</label>
          <input className={`${inputCls} w-20`} type="number" value={stopLoss} onChange={(e) => setStopLoss(e.target.value)} />
        </div>
        <div>
          <label className={labelCls}>Take Profit %</label>
          <input className={`${inputCls} w-20`} type="number" value={takeProfit} onChange={(e) => setTakeProfit(e.target.value)} />
        </div>
      </div>

      {/* Row 3: Signal Thresholds */}
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className={labelCls}>Buy Threshold</label>
          <input
            className={`${inputCls} w-24`}
            type="number"
            step="0.05"
            min="0.05"
            max="0.80"
            value={buyThreshold}
            onChange={(e) => setBuyThreshold(e.target.value)}
          />
        </div>
        <div>
          <label className={labelCls}>Sell Threshold</label>
          <input
            className={`${inputCls} w-24`}
            type="number"
            step="0.05"
            min="-0.80"
            max="-0.05"
            value={sellThreshold}
            onChange={(e) => setSellThreshold(e.target.value)}
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="bg-accent hover:bg-accent-light disabled:opacity-50 text-white rounded-lg px-5 py-2 text-sm font-medium transition-colors duration-150"
        >
          {loading ? "Running..." : "Run Backtest"}
        </button>
      </div>
    </form>
  );
}
