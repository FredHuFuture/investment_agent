import { useApi } from "../../hooks/useApi";
import { getDailyReturn } from "../../api/endpoints";
import type { DailyReturn } from "../../api/types";
import MetricCard from "../shared/MetricCard";
import { SkeletonCard } from "../ui/Skeleton";
import { formatCurrency } from "../../lib/formatters";

export default function DailyReturnCard() {
  const { data, loading, error } = useApi<DailyReturn>(
    () => getDailyReturn(),
    { cacheKey: "dashboard:dailyReturn", ttlMs: 30_000 },
  );

  if (loading) return <SkeletonCard />;

  if (error || !data) {
    return <MetricCard label="Today's Return" value="--" />;
  }

  const sign = data.return_dollars >= 0 ? "+" : "";
  const trend: "up" | "down" = data.return_dollars >= 0 ? "up" : "down";

  return (
    <MetricCard
      label="Today's Return"
      value={`${sign}${formatCurrency(data.return_dollars)}`}
      sub={`${sign}${data.return_pct.toFixed(2)}%`}
      trend={trend}
    />
  );
}
