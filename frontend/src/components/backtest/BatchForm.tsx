import { useState } from "react";

interface Props {
  onSubmit: (params: {
    tickers: string[];
    agent_combos: string[][];
    start_date: string;
    end_date: string;
    initial_capital: number;
    position_size_pct: number;
    rebalance_frequency: string;
  }) => void;
  loading?: boolean;
}

export default function BatchForm({ onSubmit, loading }: Props) {
  const [tickers, setTickers] = useState("AAPL,MSFT,NVDA,SPY,BTC");
  const [startDate, setStartDate] = useState("2022-01-01");
  const [endDate, setEndDate] = useState("2025-12-31");
  const [capital, setCapital] = useState("100000");
  const [frequency, setFrequency] = useState("weekly");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const tickerList = tickers.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean);
    if (tickerList.length === 0) return;
    onSubmit({
      tickers: tickerList,
      agent_combos: [["TechnicalAgent"]],
      start_date: startDate,
      end_date: endDate,
      initial_capital: parseFloat(capital),
      position_size_pct: 1.0,
      rebalance_frequency: frequency,
    });
  }

  const inputCls =
    "bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:border-accent";

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-gray-500 mb-1">Tickers (comma-separated)</label>
          <input className={`${inputCls} w-full`} value={tickers} onChange={(e) => setTickers(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Start</label>
          <input className={inputCls} type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">End</label>
          <input className={inputCls} type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Capital</label>
          <input className={`${inputCls} w-28`} type="number" value={capital} onChange={(e) => setCapital(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Frequency</label>
          <select className={inputCls} value={frequency} onChange={(e) => setFrequency(e.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
      </div>
      <button
        type="submit"
        disabled={loading}
        className="px-4 py-1.5 bg-accent hover:bg-accent-light disabled:opacity-50 rounded-md text-sm font-medium"
      >
        {loading ? "Running batch..." : "Run Batch Backtest"}
      </button>
    </form>
  );
}
