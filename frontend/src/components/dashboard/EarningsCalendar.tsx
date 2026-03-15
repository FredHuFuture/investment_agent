import { useApi } from "../../hooks/useApi";
import { getUpcomingEarnings } from "../../api/endpoints";
import type { EarningsEvent } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import EmptyState from "../shared/EmptyState";

function urgencyColor(daysUntil: number): string {
  if (daysUntil < 7) return "text-red-400";
  if (daysUntil <= 14) return "text-yellow-400";
  return "text-emerald-400";
}

function urgencyBadgeBg(daysUntil: number): string {
  if (daysUntil < 7) return "bg-red-500/20 text-red-400";
  if (daysUntil <= 14) return "bg-yellow-500/20 text-yellow-400";
  return "bg-emerald-500/20 text-emerald-400";
}

export default function EarningsCalendar() {
  const { data, loading, error } = useApi<EarningsEvent[]>(
    () => getUpcomingEarnings(),
    { cacheKey: "dashboard:earnings", ttlMs: 60_000 },
  );

  if (loading) {
    return (
      <Card>
        <CardHeader title="Upcoming Earnings" />
        <CardBody>
          <div className="space-y-3">
            <Skeleton variant="text" lines={4} />
          </div>
        </CardBody>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader title="Upcoming Earnings" />
        <CardBody>
          <p className="text-xs text-red-400">Failed to load earnings data.</p>
        </CardBody>
      </Card>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader title="Upcoming Earnings" />
        <CardBody>
          <EmptyState message="No upcoming earnings in the next 60 days." />
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Upcoming Earnings" />
      <CardBody>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800/50">
                <th className="text-left py-2 pr-4">Ticker</th>
                <th className="text-left py-2 px-4">Date</th>
                <th className="text-right py-2 px-4">Days Until</th>
                <th className="text-right py-2 pl-4">EPS Est.</th>
              </tr>
            </thead>
            <tbody>
              {data.map((event) => (
                <tr
                  key={event.ticker}
                  className="border-b border-gray-800/30 last:border-0"
                >
                  <td className="py-2 pr-4 font-mono font-medium text-white">
                    {event.ticker}
                  </td>
                  <td className="py-2 px-4 text-gray-300">
                    {new Date(event.earnings_date + "T00:00:00").toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </td>
                  <td className="py-2 px-4 text-right">
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${urgencyBadgeBg(event.days_until)}`}
                    >
                      {event.days_until}d
                    </span>
                  </td>
                  <td className={`py-2 pl-4 text-right ${urgencyColor(event.days_until)}`}>
                    {event.estimate_eps != null
                      ? `$${event.estimate_eps.toFixed(2)}`
                      : "--"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardBody>
    </Card>
  );
}
