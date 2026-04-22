import type { DailyPnlPoint } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import EmptyState from "../shared/EmptyState";
import { formatCurrency } from "../../lib/formatters";

interface Props {
  data: DailyPnlPoint[];
}

export function getCellColor(pnl: number | null): string {
  if (pnl === null) return "bg-gray-800/40";
  if (pnl > 1000) return "bg-green-600/80";
  if (pnl > 100) return "bg-green-600/50";
  if (pnl > 0) return "bg-green-600/25";
  if (pnl === 0) return "bg-gray-700/50";
  if (pnl > -100) return "bg-red-600/25";
  if (pnl > -1000) return "bg-red-600/50";
  return "bg-red-600/80";
}

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface Cell {
  date: string | null;
  pnl: number | null;
}

/**
 * Build a 7-row (Mon–Sun) × N-week grid ending at the last data date.
 * Weeks go left-to-right; days top-to-bottom.
 * Missing days within the range show as null cells.
 */
function buildGrid(data: DailyPnlPoint[]): Cell[][] {
  if (data.length === 0) return [];
  const byDate = new Map(data.map((p) => [p.date, p.pnl]));

  const firstPoint = data[0];
  const lastPoint = data[data.length - 1];
  if (!firstPoint || !lastPoint) return [];

  const end = new Date(lastPoint.date + "T00:00:00Z");
  const start = new Date(firstPoint.date + "T00:00:00Z");

  // Align start to Monday of its week (Mon=1..Sun=0 via getUTCDay())
  const startDay = start.getUTCDay();       // 0=Sun, 1=Mon, ... 6=Sat
  const daysToMon = (startDay + 6) % 7;    // Mon=0, Tue=1, ..., Sun=6
  const alignedStart = new Date(start);
  alignedStart.setUTCDate(start.getUTCDate() - daysToMon);

  const weeks: Cell[][] = [];
  const cursor = new Date(alignedStart);
  while (cursor <= end) {
    const week: Cell[] = [];
    for (let d = 0; d < 7; d++) {
      const iso = cursor.toISOString().slice(0, 10);
      const within = cursor >= start && cursor <= end;
      week.push({
        date: within ? iso : null,
        pnl: within ? (byDate.get(iso) ?? null) : null,
      });
      cursor.setUTCDate(cursor.getUTCDate() + 1);
    }
    weeks.push(week);
  }
  return weeks;
}

export default function DailyPnlHeatmap({ data }: Props) {
  if (data.length === 0) {
    return (
      <Card>
        <CardHeader title="Daily P&L Heatmap" />
        <CardBody>
          <EmptyState message="Run a health check to generate daily P&L data." />
        </CardBody>
      </Card>
    );
  }

  const weeks = buildGrid(data);

  return (
    <Card>
      <CardHeader
        title="Daily P&L Heatmap"
        subtitle="Calendar view; hover a cell for exact P&L"
      />
      <CardBody>
        <div className="overflow-x-auto">
          <div className="flex gap-1">
            {/* Weekday labels column */}
            <div className="flex flex-col gap-1 pr-1">
              {WEEKDAY_LABELS.map((label) => (
                <div
                  key={label}
                  className="h-3 text-[10px] text-gray-500 flex items-center"
                >
                  {label}
                </div>
              ))}
            </div>

            {/* Week columns */}
            {weeks.map((week, wi) => (
              <div key={wi} className="flex flex-col gap-1">
                {week.map((cell, di) => {
                  const titleAttr =
                    cell.date && cell.pnl !== null
                      ? `${cell.date}: ${cell.pnl >= 0 ? "+" : ""}${formatCurrency(cell.pnl)}`
                      : cell.date
                      ? `${cell.date}: --`
                      : "";
                  return (
                    <div
                      key={`${wi}-${di}`}
                      data-testid={
                        cell.date ? `daily-pnl-cell-${cell.date}` : undefined
                      }
                      className={`h-3 w-3 rounded-sm ${getCellColor(cell.pnl)}`}
                      title={titleAttr}
                      tabIndex={cell.date ? 0 : -1}
                      aria-label={titleAttr || undefined}
                      role={cell.date ? "img" : undefined}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
