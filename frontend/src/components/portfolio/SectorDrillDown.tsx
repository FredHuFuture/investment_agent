import { useEffect, useCallback, useMemo } from "react";
import type { Position } from "../../api/types";
import { Card } from "../ui/Card";
import { Button } from "../ui/Button";
import { formatCurrency, pnlColor } from "../../lib/formatters";

interface Props {
  sector: string | null;
  positions: Position[];
  onClose: () => void;
}

export default function SectorDrillDown({ sector, positions, onClose }: Props) {
  const handleEscape = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (!sector) return;
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [sector, handleEscape]);

  const filtered = useMemo(() => {
    if (!sector) return [];
    return positions.filter(
      (pos) => pos.sector?.toLowerCase() === sector.toLowerCase(),
    );
  }, [sector, positions]);

  const totalMktVal = useMemo(
    () => filtered.reduce((s, p) => s + p.market_value, 0),
    [filtered],
  );

  const avgPnlPct = useMemo(() => {
    if (filtered.length === 0) return 0;
    const sum = filtered.reduce((s, p) => s + p.unrealized_pnl_pct, 0);
    return (sum / filtered.length) * 100;
  }, [filtered]);

  if (!sector) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
      <div onClick={(e) => e.stopPropagation()}>
      <Card
        padding="none"
        className="w-full max-w-xl mx-4 shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800/50">
          <div>
            <h2 className="text-base font-semibold text-white">{sector}</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {filtered.length} position{filtered.length !== 1 ? "s" : ""}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>

        {/* Summary row */}
        <div className="grid grid-cols-2 gap-4 px-5 py-3 border-b border-gray-800/30 bg-gray-900/30">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-gray-500">
              Total Mkt Value
            </p>
            <p className="text-sm font-medium text-gray-200">
              {formatCurrency(totalMktVal)}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-gray-500">
              Avg P&L %
            </p>
            <p className={`text-sm font-medium ${pnlColor(avgPnlPct)}`}>
              {avgPnlPct > 0 ? "+" : ""}
              {avgPnlPct.toFixed(1)}%
            </p>
          </div>
        </div>

        {/* Positions table */}
        <div className="overflow-x-auto max-h-80 overflow-y-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800/50 bg-gray-900/30">
                <th className="px-5 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                  Ticker
                </th>
                <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                  Qty
                </th>
                <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                  Price
                </th>
                <th className="px-3 py-2 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold">
                  P&L %
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((pos) => (
                <tr
                  key={pos.ticker}
                  className="border-b border-gray-800/30 hover:bg-gray-800/40 transition-colors"
                >
                  <td className="px-5 py-2 font-mono font-semibold text-white">
                    {pos.ticker}
                  </td>
                  <td className="px-3 py-2 text-gray-300">
                    {pos.quantity < 1 ? pos.quantity.toFixed(6) : pos.quantity.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 text-gray-300">
                    {formatCurrency(pos.current_price)}
                  </td>
                  <td
                    className={`px-3 py-2 font-medium ${pnlColor(pos.unrealized_pnl_pct)}`}
                  >
                    {pos.unrealized_pnl_pct > 0 ? "+" : ""}
                    {(pos.unrealized_pnl_pct * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-5 py-8 text-center text-gray-500 text-sm"
                  >
                    No positions in this sector.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
      </div>
    </div>
  );
}
