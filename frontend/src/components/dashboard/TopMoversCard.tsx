import { useMemo } from "react";
import { Link } from "react-router-dom";
import type { Position } from "../../api/types";
import { Card, CardHeader, CardBody } from "../../components/ui/Card";
import EmptyState from "../../components/shared/EmptyState";
import { formatPct } from "../../lib/formatters";

interface TopMoversCardProps {
  positions: Position[];
}

export default function TopMoversCard({ positions }: TopMoversCardProps) {
  const { gainers, losers } = useMemo(() => {
    const sorted = [...positions].sort(
      (a, b) => b.unrealized_pnl_pct - a.unrealized_pnl_pct,
    );
    const g = sorted.filter((p) => p.unrealized_pnl_pct > 0).slice(0, 3);
    const l = sorted
      .filter((p) => p.unrealized_pnl_pct < 0)
      .slice(-3)
      .reverse();
    return { gainers: g, losers: l };
  }, [positions]);

  if (positions.length === 0) {
    return (
      <Card>
        <CardHeader title="Top Movers" />
        <CardBody>
          <EmptyState message="No positions yet." />
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Top Movers" />
      <CardBody>
        <div className="grid grid-cols-2 gap-4">
          {/* Gainers column */}
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Gainers
            </h4>
            {gainers.length === 0 ? (
              <p className="text-xs text-gray-600">None</p>
            ) : (
              <ul className="space-y-1.5">
                {gainers.map((pos) => (
                  <li key={pos.ticker} className="flex items-center gap-2">
                    <Link
                      to={`/portfolio/${pos.ticker}`}
                      className="font-mono text-sm font-medium text-white hover:text-accent-light transition-colors w-14 shrink-0"
                    >
                      {pos.ticker}
                    </Link>
                    <span className="text-sm font-medium text-emerald-400">
                      {formatPct(pos.unrealized_pnl_pct * 100)}
                    </span>
                    <svg
                      className="w-3 h-3 text-emerald-400 shrink-0"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M18 15l-6-6-6 6" />
                    </svg>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Losers column */}
          <div>
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Losers
            </h4>
            {losers.length === 0 ? (
              <p className="text-xs text-gray-600">None</p>
            ) : (
              <ul className="space-y-1.5">
                {losers.map((pos) => (
                  <li key={pos.ticker} className="flex items-center gap-2">
                    <Link
                      to={`/portfolio/${pos.ticker}`}
                      className="font-mono text-sm font-medium text-white hover:text-accent-light transition-colors w-14 shrink-0"
                    >
                      {pos.ticker}
                    </Link>
                    <span className="text-sm font-medium text-red-400">
                      {formatPct(pos.unrealized_pnl_pct * 100)}
                    </span>
                    <svg
                      className="w-3 h-3 text-red-400 shrink-0"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M6 9l6 6 6-6" />
                    </svg>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
