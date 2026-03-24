import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { getDividends, addDividend } from "../../api/endpoints";
import type { DividendSummary } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import EmptyState from "../shared/EmptyState";
import { useToast } from "../../contexts/ToastContext";
import { formatCurrency, formatDate } from "../../lib/formatters";

interface DividendTrackerProps {
  ticker: string;
}

export default function DividendTracker({ ticker }: DividendTrackerProps) {
  const api = useApi<DividendSummary>(
    () => getDividends(ticker),
    [ticker],
  );
  const { toast } = useToast();

  const [amountPerShare, setAmountPerShare] = useState("");
  const [exDate, setExDate] = useState("");
  const [payDate, setPayDate] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const amt = parseFloat(amountPerShare);
    if (isNaN(amt) || amt <= 0) {
      toast.error("Invalid amount", "Amount per share must be a positive number.");
      return;
    }
    if (!exDate) {
      toast.error("Missing date", "Ex-date is required.");
      return;
    }

    setSubmitting(true);
    try {
      await addDividend(ticker, {
        amount_per_share: amt,
        ex_date: exDate,
        pay_date: payDate || undefined,
      });
      toast.success("Dividend recorded");
      setAmountPerShare("");
      setExDate("");
      setPayDate("");
      api.refetch();
    } catch (err) {
      toast.error("Failed to record dividend", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Dividends" />
      <CardBody>
        {api.loading && (
          <div className="space-y-3">
            <Skeleton variant="text" width="50%" height={14} />
            <Skeleton variant="rectangular" height={80} />
          </div>
        )}

        {api.error && (
          <p className="text-gray-500 text-sm">
            Could not load dividend data.
          </p>
        )}

        {api.data && (
          <div className="space-y-4">
            {/* Summary metrics */}
            <div className="flex flex-wrap gap-6">
              <div>
                <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-0.5">
                  Total Dividends
                </div>
                <div className="text-lg font-semibold text-emerald-400 font-mono">
                  {formatCurrency(api.data.total_dividends)}
                </div>
              </div>
              <div>
                <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-0.5">
                  Yield on Cost
                </div>
                <div className="text-lg font-semibold text-gray-200 font-mono">
                  {api.data.yield_on_cost_pct.toFixed(2)}%
                </div>
              </div>
            </div>

            {/* Entries table */}
            {api.data.entries.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm table-auto">
                  <thead>
                    <tr className="border-b border-gray-800/50">
                      <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                        Ex-Date
                      </th>
                      <th className="px-3 py-2 text-right text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                        $/Share
                      </th>
                      <th className="px-3 py-2 text-right text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                        Total
                      </th>
                      <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                        Pay Date
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {api.data.entries.map((entry) => (
                      <tr
                        key={entry.id}
                        className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors"
                      >
                        <td className="px-3 py-2 whitespace-nowrap text-gray-400 text-xs">
                          {formatDate(entry.ex_date)}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-right text-gray-300 font-mono text-xs">
                          ${entry.amount_per_share.toFixed(4)}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-right text-emerald-400 font-mono text-xs">
                          {formatCurrency(entry.total_amount)}
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap text-gray-500 text-xs">
                          {entry.pay_date ? formatDate(entry.pay_date) : "--"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState message="No dividends recorded yet." />
            )}

            {/* Add dividend form */}
            <form onSubmit={handleSubmit} className="pt-3 border-t border-gray-800/50">
              <div className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold mb-2">
                Record Dividend
              </div>
              <div className="flex flex-wrap items-end gap-3">
                <div className="flex flex-col">
                  <label htmlFor="div-amount" className="text-[10px] text-gray-500 mb-1">
                    $/Share
                  </label>
                  <input
                    id="div-amount"
                    type="number"
                    step="any"
                    min="0"
                    placeholder="0.50"
                    value={amountPerShare}
                    onChange={(e) => setAmountPerShare(e.target.value)}
                    className="w-28 rounded-md bg-gray-800/60 border border-gray-700/50 px-2.5 py-1.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-accent/50"
                    required
                  />
                </div>
                <div className="flex flex-col">
                  <label htmlFor="div-ex-date" className="text-[10px] text-gray-500 mb-1">
                    Ex-Date
                  </label>
                  <input
                    id="div-ex-date"
                    type="date"
                    value={exDate}
                    onChange={(e) => setExDate(e.target.value)}
                    className="w-36 rounded-md bg-gray-800/60 border border-gray-700/50 px-2.5 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-accent/50"
                    required
                  />
                </div>
                <div className="flex flex-col">
                  <label htmlFor="div-pay-date" className="text-[10px] text-gray-500 mb-1">
                    Pay Date
                  </label>
                  <input
                    id="div-pay-date"
                    type="date"
                    value={payDate}
                    onChange={(e) => setPayDate(e.target.value)}
                    className="w-36 rounded-md bg-gray-800/60 border border-gray-700/50 px-2.5 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-accent/50"
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 rounded-md bg-accent hover:bg-accent-light text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {submitting ? "Recording..." : "Record"}
                </button>
              </div>
            </form>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
