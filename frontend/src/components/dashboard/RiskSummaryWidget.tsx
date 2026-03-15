import { Link } from "react-router-dom";
import { useApi } from "../../hooks/useApi";
import { getPortfolioRisk } from "../../api/endpoints";
import type { PortfolioRisk } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";

/** Traffic-light color helpers */
function drawdownColor(pct: number): string {
  const abs = Math.abs(pct);
  if (abs < 5) return "bg-green-400";
  if (abs <= 15) return "bg-yellow-400";
  return "bg-red-400";
}

function sharpeColor(ratio: number | null): string {
  if (ratio == null) return "bg-gray-500";
  if (ratio > 1.5) return "bg-green-400";
  if (ratio >= 0.5) return "bg-yellow-400";
  return "bg-red-400";
}

function varColor(varPct: number): string {
  const abs = Math.abs(varPct);
  if (abs < 2) return "bg-green-400";
  if (abs <= 5) return "bg-yellow-400";
  return "bg-red-400";
}

function formatPct(v: number): string {
  return `${v >= 0 ? "" : "-"}${Math.abs(v).toFixed(2)}%`;
}

interface MetricRowProps {
  dotClass: string;
  label: string;
  value: string;
}

function MetricRow({ dotClass, label, value }: MetricRowProps) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <div className="flex items-center gap-2">
        <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${dotClass}`} />
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <span className="text-sm font-mono text-gray-200">{value}</span>
    </div>
  );
}

export default function RiskSummaryWidget() {
  const { data, loading, error } = useApi<PortfolioRisk>(
    () => getPortfolioRisk(),
    { cacheKey: "dashboard:riskSummary", ttlMs: 60_000 },
  );

  if (loading) return <SkeletonCard />;

  if (error || !data) {
    return (
      <Card>
        <CardHeader title="Risk Overview" />
        <CardBody>
          <p className="text-sm text-gray-500">Unable to load risk data.</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Risk Overview" />
      <CardBody>
        <div className="space-y-1">
          <MetricRow
            dotClass={drawdownColor(data.current_drawdown_pct)}
            label="Current Drawdown"
            value={formatPct(data.current_drawdown_pct)}
          />
          <MetricRow
            dotClass={sharpeColor(data.sharpe_ratio)}
            label="Sharpe Ratio"
            value={data.sharpe_ratio != null ? data.sharpe_ratio.toFixed(2) : "--"}
          />
          <MetricRow
            dotClass={varColor(data.var_95)}
            label="VaR (95%)"
            value={formatPct(data.var_95)}
          />
        </div>

        <div className="mt-4 pt-3 border-t border-gray-800/50">
          <Link
            to="/risk"
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors duration-150"
          >
            View Details &rarr;
          </Link>
        </div>
      </CardBody>
    </Card>
  );
}
