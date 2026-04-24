import { LineChart, Line, YAxis } from "recharts";

export interface ICSparklineProps {
  agentName: string;
  rollingIc: (number | null)[];
  icIr: number | null;
}

/**
 * Determine sparkline stroke color from IC-IR value.
 * > 1.0 → green, 0.5–1.0 → amber, < 0.5 (incl. negative) → red, null → gray.
 */
export function sparklineColor(icIr: number | null): string {
  if (icIr === null) return "#6B7280";
  if (icIr > 1.0) return "#10B981";
  if (icIr >= 0.5) return "#F59E0B";
  return "#EF4444";
}

/**
 * 60×20px Recharts LineChart sparkline of rolling IC values.
 * Renders an empty-state span when rollingIc has fewer than 1 point.
 */
export default function ICSparkline({ agentName, rollingIc, icIr }: ICSparklineProps) {
  if (rollingIc.length === 0) {
    return (
      <span
        data-testid={`cal-ic-sparkline-empty-${agentName}`}
        className="text-xs text-gray-600"
        title="IC history accumulates as the corpus grows"
      >
        No IC history
      </span>
    );
  }

  // Recharts requires non-null numeric values; replace null with 0 for rendering.
  const data = rollingIc.map((v, i) => ({ idx: i, ic: v ?? 0 }));
  const stroke = sparklineColor(icIr);

  return (
    <div
      data-testid={`cal-ic-sparkline-${agentName}`}
      data-stroke={stroke}
      className="inline-block"
      style={{ width: 60, height: 20 }}
      aria-label={`90-day IC trend for ${agentName}`}
      role="img"
    >
      <LineChart
        width={60}
        height={20}
        data={data}
        margin={{ top: 2, bottom: 2, left: 0, right: 0 }}
      >
        <YAxis hide domain={["auto", "auto"]} />
        <Line
          type="monotone"
          dataKey="ic"
          stroke={stroke}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </div>
  );
}
