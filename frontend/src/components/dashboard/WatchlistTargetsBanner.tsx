import { Link } from "react-router-dom";
import { useApi } from "../../hooks/useApi";
import { getWatchlistTargets } from "../../api/endpoints";
import type { WatchlistTarget } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { formatCurrency } from "../../lib/formatters";

/** Color class for the distance badge based on how close price is to target. */
function distanceColor(pct: number): string {
  if (pct <= 0) return "bg-green-500/20 text-green-400";
  if (pct <= 5) return "bg-yellow-500/20 text-yellow-400";
  return "bg-orange-500/20 text-orange-400";
}

/** Dot color for the left indicator. */
function dotColor(pct: number): string {
  if (pct <= 0) return "bg-green-400";
  if (pct <= 5) return "bg-yellow-400";
  return "bg-orange-400";
}

export default function WatchlistTargetsBanner() {
  const { data, loading, error } = useApi<WatchlistTarget[]>(
    () => getWatchlistTargets(),
    { cacheKey: "dashboard:watchlistTargets", ttlMs: 120_000 },
  );

  // Hide completely if loading, error, or no items
  if (loading || error || !data || data.length === 0) return null;

  return (
    <Card>
      <CardHeader
        title="Watchlist Near Target"
        action={
          <Link
            to="/watchlist"
            className="text-xs text-accent-light hover:text-accent transition-colors duration-150"
          >
            View all &rarr;
          </Link>
        }
      />
      <CardBody>
        <div className="flex flex-wrap gap-3">
          {data.map((item) => (
            <Link
              key={item.ticker}
              to={`/analyze/${item.ticker}`}
              className="flex items-center gap-3 rounded-lg bg-gray-800/50 border border-gray-700/50 px-4 py-3 hover:border-accent/40 transition-colors duration-150 min-w-[200px]"
            >
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${dotColor(item.distance_pct)}`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-medium text-white text-sm">
                    {item.ticker}
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-xs font-medium ${distanceColor(item.distance_pct)}`}
                  >
                    {item.distance_pct <= 0 ? "" : "+"}
                    {item.distance_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center justify-between gap-2 mt-1">
                  <span className="text-xs text-gray-400">
                    {formatCurrency(item.current_price)}
                  </span>
                  <span className="text-xs text-gray-500">
                    target {formatCurrency(item.target_buy_price)}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
