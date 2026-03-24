const COLORS = [
  "#32af78", "#34d399", "#fbbf24", "#f87171", "#a78bfa",
  "#fb923c", "#2dd4bf", "#e879f9", "#94a3b8", "#38bdf8",
];

interface Props {
  allocations: Record<string, number>;
}

export default function AllocationChart({ allocations }: Props) {
  const entries = Object.entries(allocations)
    .map(([name, value]) => ({ name, pct: Math.round(value * 1000) / 10 }))
    .sort((a, b) => b.pct - a.pct);

  if (entries.length === 0) return null;

  // SVG donut chart
  const size = 180;
  const stroke = 24;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  let accumulated = 0;
  const arcs = entries.map((entry, i) => {
    const dashLength = (entry.pct / 100) * circumference;
    const dashOffset = -(accumulated / 100) * circumference;
    accumulated += entry.pct;
    return { ...entry, dashLength, dashOffset, color: COLORS[i % COLORS.length] };
  });

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Donut */}
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background ring */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="rgba(55,65,81,0.25)"
          strokeWidth={stroke}
        />
        {/* Segments */}
        {arcs.map((arc) => (
          <circle
            key={arc.name}
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={arc.color}
            strokeWidth={stroke}
            strokeDasharray={`${arc.dashLength} ${circumference - arc.dashLength}`}
            strokeDashoffset={arc.dashOffset}
            strokeLinecap="butt"
            transform={`rotate(-90 ${center} ${center})`}
          />
        ))}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap justify-center gap-x-3 gap-y-1">
        {arcs.map((arc) => (
          <div key={arc.name} className="flex items-center gap-1.5 text-xs">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: arc.color }}
            />
            <span className="text-gray-400">{arc.name}</span>
            <span className="font-mono text-gray-500">{arc.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
