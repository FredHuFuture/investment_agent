import type { ReturnsResponse } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import EmptyState from "../shared/EmptyState";

interface Props {
  data: ReturnsResponse | null;
  loading: boolean;
  error: string | null;
}

function fmtPct(v: number | null): string {
  if (v === null) return "--";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function trendColor(v: number | null): string {
  if (v === null) return "text-gray-500";
  if (v > 0) return "text-green-400";
  if (v < 0) return "text-red-400";
  return "text-gray-400";
}

export default function TtwrorMetricCard({ data, loading, error }: Props) {
  if (loading) return <SkeletonCard className="h-[240px]" />;
  if (error) {
    return (
      <Card>
        <CardHeader title="Time-Weighted Return & IRR" />
        <CardBody>
          <EmptyState message={error} />
        </CardBody>
      </Card>
    );
  }
  if (!data) return null;

  const { aggregate, positions } = data;
  const sparse = aggregate.snapshot_count < 2;

  return (
    <Card>
      <CardHeader
        title="Time-Weighted Return & IRR"
        subtitle={`${aggregate.window_days}-day window · ${aggregate.snapshot_count} snapshots`}
      />
      <CardBody>
        {sparse ? (
          <EmptyState message="Need at least 2 portfolio snapshots. Run a health check to generate performance data." />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-gray-500 uppercase tracking-wider">TTWROR</div>
                <div
                  data-testid="ttwror-value"
                  className={`text-3xl font-semibold ${trendColor(aggregate.ttwror)}`}
                >
                  {fmtPct(aggregate.ttwror)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 uppercase tracking-wider">IRR (annualized)</div>
                <div
                  data-testid="irr-value"
                  className={`text-3xl font-semibold ${trendColor(aggregate.irr)}`}
                >
                  {fmtPct(aggregate.irr)}
                </div>
              </div>
            </div>

            {positions.length > 0 && (
              <div className="overflow-x-auto pt-2 border-t border-gray-800/50">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-gray-500 text-xs uppercase tracking-wider">
                      <th className="text-left py-2 pr-4">Ticker</th>
                      <th className="text-right py-2 px-4">TTWROR</th>
                      <th className="text-right py-2 px-4">IRR</th>
                      <th className="text-right py-2 pl-4">Hold Days</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p) => (
                      <tr
                        key={p.ticker}
                        className={`border-b border-gray-800/30 ${p.status === "closed" ? "text-gray-500" : ""}`}
                      >
                        <td className="py-2 pr-4 font-mono text-white font-medium">
                          {p.ticker}
                          {p.status === "closed" && (
                            <span className="ml-2 text-xs text-gray-600">(closed)</span>
                          )}
                        </td>
                        <td
                          data-testid={`position-ttwror-${p.ticker}`}
                          className={`py-2 px-4 text-right ${trendColor(p.ttwror)}`}
                        >
                          {fmtPct(p.ttwror)}
                        </td>
                        <td
                          data-testid={`position-irr-${p.ticker}`}
                          className={`py-2 px-4 text-right ${trendColor(p.irr)}`}
                        >
                          {fmtPct(p.irr)}
                        </td>
                        <td className="py-2 pl-4 text-right text-gray-400">{p.hold_days}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
