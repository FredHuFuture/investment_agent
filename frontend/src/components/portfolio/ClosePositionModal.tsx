import { useState } from "react";
import type { Position } from "../../api/types";
import { formatCurrency } from "../../lib/formatters";

interface Props {
  position: Position;
  onClose: () => void;
  onConfirm: (data: {
    exit_price: number;
    exit_reason: string;
    exit_date?: string;
  }) => Promise<void>;
}

export default function ClosePositionModal({
  position,
  onClose,
  onConfirm,
}: Props) {
  const [exitPrice, setExitPrice] = useState(
    position.current_price > 0
      ? String(position.current_price)
      : "",
  );
  const [exitReason, setExitReason] = useState("manual");
  const [exitDate, setExitDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const price = parseFloat(exitPrice) || 0;
  const realizedPnl = (price - position.avg_cost) * position.quantity;
  const returnPct =
    position.avg_cost > 0 ? ((price - position.avg_cost) / position.avg_cost) * 100 : 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (price <= 0) {
      setError("Exit price must be greater than 0.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await onConfirm({
        exit_price: price,
        exit_reason: exitReason,
        exit_date: exitDate || undefined,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to close position");
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md rounded-xl bg-gray-900 border border-gray-700 p-6 shadow-2xl">
        <h2 className="text-lg font-semibold text-white mb-1">
          Close Position: {position.ticker}
        </h2>
        <p className="text-sm text-gray-400 mb-5">
          {position.quantity} shares @ {formatCurrency(position.avg_cost)} avg
        </p>

        {error && (
          <div className="mb-4 rounded-md bg-red-900/40 border border-red-700/50 px-3 py-2 text-sm text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Exit Price
            </label>
            <input
              type="number"
              step="any"
              value={exitPrice}
              onChange={(e) => setExitPrice(e.target.value)}
              className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Reason</label>
            <select
              value={exitReason}
              onChange={(e) => setExitReason(e.target.value)}
              className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="manual">Manual</option>
              <option value="target_hit">Target Hit</option>
              <option value="stop_loss">Stop Loss</option>
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Exit Date
            </label>
            <input
              type="date"
              value={exitDate}
              onChange={(e) => setExitDate(e.target.value)}
              className="w-full rounded-md bg-gray-800 border border-gray-700 px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* P&L preview */}
          {price > 0 && (
            <div className="rounded-lg bg-gray-800/50 border border-gray-700/50 px-4 py-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Realized P&L</span>
                <span
                  className={`font-medium ${realizedPnl >= 0 ? "text-emerald-400" : "text-red-400"}`}
                >
                  {realizedPnl >= 0 ? "+" : ""}
                  {formatCurrency(realizedPnl)} ({returnPct >= 0 ? "+" : ""}
                  {returnPct.toFixed(1)}%)
                </span>
              </div>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-md border border-gray-600 px-4 py-2 text-sm text-gray-300 hover:bg-gray-800 transition-colors"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || price <= 0}
              className="flex-1 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50 transition-colors"
            >
              {submitting ? "Closing..." : "Close Position"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
