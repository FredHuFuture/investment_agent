import { useState } from "react";
import { compareSnapshots } from "../../api/endpoints";
import type { SnapshotComparison as SnapshotComparisonType } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { formatCurrency } from "../../lib/formatters";

export default function SnapshotComparison() {
  const [dateA, setDateA] = useState("");
  const [dateB, setDateB] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SnapshotComparisonType | null>(null);
  const { toast } = useToast();

  async function handleCompare() {
    if (!dateA || !dateB) {
      toast.error("Please select both dates.");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await compareSnapshots(dateA, dateB);
      setResult(res.data);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to compare snapshots.";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  const changePositive = result ? result.value_change >= 0 : false;

  return (
    <Card>
      <CardHeader title="Portfolio Snapshot Comparison" subtitle="Compare portfolio state between two dates" />
      <CardBody>
        {/* Date pickers and compare button */}
        <div className="flex flex-wrap items-end gap-4 mb-6">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Date A</label>
            <input
              type="date"
              value={dateA}
              onChange={(e) => setDateA(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Date B</label>
            <input
              type="date"
              value={dateB}
              onChange={(e) => setDateB(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <Button onClick={handleCompare} disabled={loading} size="sm">
            {loading ? "Comparing..." : "Compare"}
          </Button>
        </div>

        {/* Results */}
        {result && (
          <div className="space-y-6">
            {/* Value comparison summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-gray-400">Value (A)</p>
                <p className="text-lg font-semibold text-white">
                  {formatCurrency(result.total_value_a)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Value (B)</p>
                <p className="text-lg font-semibold text-white">
                  {formatCurrency(result.total_value_b)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Change</p>
                <p
                  className={`text-lg font-semibold ${
                    changePositive ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {changePositive ? "+" : ""}
                  {formatCurrency(result.value_change)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Change %</p>
                <p
                  className={`text-lg font-semibold ${
                    changePositive ? "text-green-400" : "text-red-400"
                  }`}
                >
                  {changePositive ? "+" : ""}
                  {result.value_change_pct.toFixed(2)}%
                </p>
              </div>
            </div>

            {/* Positions added / removed */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.positions_added.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-green-400 mb-2">
                    Positions Added
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {result.positions_added.map((ticker) => (
                      <span
                        key={ticker}
                        className="bg-green-900/30 text-green-400 text-xs font-mono px-2 py-1 rounded"
                      >
                        {ticker}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {result.positions_removed.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-red-400 mb-2">
                    Positions Removed
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {result.positions_removed.map((ticker) => (
                      <span
                        key={ticker}
                        className="bg-red-900/30 text-red-400 text-xs font-mono px-2 py-1 rounded"
                      >
                        {ticker}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Positions changed table */}
            {result.positions_changed.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-300 mb-2">
                  Positions Changed
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800/50">
                        <th className="text-left py-2 pr-4">Ticker</th>
                        <th className="text-right py-2 px-4">Value A</th>
                        <th className="text-right py-2 px-4">Value B</th>
                        <th className="text-right py-2 pl-4">Change %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.positions_changed.map((pos) => (
                        <tr
                          key={pos.ticker}
                          className="border-b border-gray-800/30 last:border-0"
                        >
                          <td className="py-2 pr-4 font-mono text-white font-medium">
                            {pos.ticker}
                          </td>
                          <td className="py-2 px-4 text-right text-gray-300">
                            {formatCurrency(pos.value_a)}
                          </td>
                          <td className="py-2 px-4 text-right text-gray-300">
                            {formatCurrency(pos.value_b)}
                          </td>
                          <td
                            className={`py-2 pl-4 text-right font-medium ${
                              pos.change_pct >= 0
                                ? "text-green-400"
                                : "text-red-400"
                            }`}
                          >
                            {pos.change_pct >= 0 ? "+" : ""}
                            {pos.change_pct.toFixed(2)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
