interface SignalStrengthGaugeProps {
  signal: string;
  confidence: number;
  rawScore: number;
  consensusScore: number;
}

// Map signal to SVG arc color
function signalArcColor(signal: string): string {
  switch (signal.toUpperCase()) {
    case "BUY":
      return "#4ade80"; // green-400
    case "SELL":
      return "#f87171"; // red-400
    default:
      return "#918b82"; // gray-400
  }
}

// Map signal to glow color (for the drop-shadow)
function signalGlow(signal: string): string {
  switch (signal.toUpperCase()) {
    case "BUY":
      return "rgba(74,222,128,0.35)";
    case "SELL":
      return "rgba(248,113,113,0.35)";
    default:
      return "rgba(156,163,175,0.2)";
  }
}

// Map signal to text Tailwind class
function signalTextClass(signal: string): string {
  switch (signal.toUpperCase()) {
    case "BUY":
      return "text-green-400";
    case "SELL":
      return "text-red-400";
    default:
      return "text-gray-400";
  }
}

/**
 * Compute SVG arc path for a semi-circle gauge.
 * The arc goes from 180deg (left) to 0deg (right) — i.e. the top half.
 * `fraction` is 0..1 representing how much of the arc to fill.
 */
function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
): string {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const x1 = cx + r * Math.cos(toRad(startAngle));
  const y1 = cy - r * Math.sin(toRad(startAngle));
  const x2 = cx + r * Math.cos(toRad(endAngle));
  const y2 = cy - r * Math.sin(toRad(endAngle));
  const sweep = endAngle - startAngle;
  const largeArc = sweep > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 0 ${x2} ${y2}`;
}

/**
 * Needle tip coordinates for a given angle on the semi-circle.
 */
function needlePoint(
  cx: number,
  cy: number,
  r: number,
  angleDeg: number,
): { x: number; y: number } {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
}

export default function SignalStrengthGauge({
  signal,
  confidence,
  rawScore,
  consensusScore,
}: SignalStrengthGaugeProps) {
  // --- Semi-circular gauge parameters ---
  const cx = 120;
  const cy = 110;
  const radius = 90;
  const strokeWidth = 14;

  // Confidence clamped 0-100
  const conf = Math.max(0, Math.min(100, confidence));

  // Angle: 180 (left, 0%) to 0 (right, 100%)
  const fillAngle = 180 - (conf / 100) * 180;

  // Background arc (full semi-circle, dark)
  const bgArc = describeArc(cx, cy, radius, 0, 180);

  // Filled arc (from left to the confidence position)
  const filledArc = conf > 0 ? describeArc(cx, cy, radius, fillAngle, 180) : "";

  // Needle position
  const needle = needlePoint(cx, cy, radius, fillAngle);

  const color = signalArcColor(signal);
  const glow = signalGlow(signal);

  // --- Raw score bar parameters ---
  const sellThreshold = -0.3;
  const buyThreshold = 0.3;
  const displayMin = -1;
  const displayMax = 1;
  const clampedRaw = Math.max(displayMin, Math.min(displayMax, rawScore));
  const rawPct = ((clampedRaw - displayMin) / (displayMax - displayMin)) * 100;
  const sellPct =
    ((sellThreshold - displayMin) / (displayMax - displayMin)) * 100;
  const buyPct =
    ((buyThreshold - displayMin) / (displayMax - displayMin)) * 100;

  return (
    <div className="flex flex-col items-center gap-5">
      {/* Semi-circular gauge */}
      <div className="relative" style={{ width: 240, height: 140 }}>
        <svg
          viewBox="0 0 240 140"
          width={240}
          height={140}
          className="overflow-visible"
        >
          {/* Glow filter */}
          <defs>
            <filter id="gauge-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background arc */}
          <path
            d={bgArc}
            fill="none"
            stroke="#161410"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />

          {/* Tick marks at 0%, 25%, 50%, 75%, 100% */}
          {[0, 25, 50, 75, 100].map((pct) => {
            const angle = 180 - (pct / 100) * 180;
            const inner = needlePoint(cx, cy, radius - strokeWidth / 2 - 2, angle);
            const outer = needlePoint(cx, cy, radius + strokeWidth / 2 + 2, angle);
            return (
              <line
                key={pct}
                x1={inner.x}
                y1={inner.y}
                x2={outer.x}
                y2={outer.y}
                stroke="#4b5563"
                strokeWidth={1.5}
              />
            );
          })}

          {/* Filled arc */}
          {conf > 0 && (
            <path
              d={filledArc}
              fill="none"
              stroke={color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              filter="url(#gauge-glow)"
            />
          )}

          {/* Needle */}
          <line
            x1={cx}
            y1={cy}
            x2={needle.x}
            y2={needle.y}
            stroke="white"
            strokeWidth={2.5}
            strokeLinecap="round"
          />
          {/* Needle center dot */}
          <circle cx={cx} cy={cy} r={5} fill="#111827" stroke="white" strokeWidth={2} />
          {/* Needle tip dot */}
          <circle
            cx={needle.x}
            cy={needle.y}
            r={4}
            fill={color}
            style={{ filter: `drop-shadow(0 0 4px ${glow})` }}
          />

          {/* "0" and "100" labels at the ends */}
          <text x={cx - radius - 10} y={cy + 18} className="fill-gray-500 text-[10px]" textAnchor="middle">
            0
          </text>
          <text x={cx + radius + 10} y={cy + 18} className="fill-gray-500 text-[10px]" textAnchor="middle">
            100
          </text>
        </svg>

        {/* Center label: signal + confidence */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-end pb-1 pointer-events-none"
          data-testid="gauge-center-label"
        >
          <span
            className={`text-2xl font-bold tracking-wide ${signalTextClass(signal)}`}
          >
            {signal.toUpperCase()}
          </span>
          <span className="text-sm text-gray-400 font-mono">
            {conf.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Details below the gauge */}
      <div className="w-full max-w-xs space-y-4">
        {/* Raw score bar */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[10px] text-gray-500 uppercase tracking-wider">
            <span>-1</span>
            <span className="text-gray-400 normal-case text-xs font-semibold">
              Raw Score
            </span>
            <span>+1</span>
          </div>
          <div className="relative h-3 rounded-full overflow-hidden bg-gray-800">
            {/* Gradient background */}
            <div
              className="absolute inset-0 rounded-full"
              style={{
                background:
                  "linear-gradient(to right, #ef4444 0%, #f59e0b 30%, #eab308 50%, #f59e0b 70%, #22c55e 100%)",
                opacity: 0.6,
              }}
            />
            {/* Sell threshold marker */}
            <div
              className="absolute top-0 h-full w-px bg-white/30"
              style={{ left: `${sellPct}%` }}
              title={`Sell threshold: ${sellThreshold}`}
            />
            {/* Buy threshold marker */}
            <div
              className="absolute top-0 h-full w-px bg-white/30"
              style={{ left: `${buyPct}%` }}
              title={`Buy threshold: ${buyThreshold}`}
            />
            {/* Raw score marker */}
            <div
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 border-white bg-gray-950 shadow-lg shadow-black/40 z-10"
              style={{ left: `${rawPct}%` }}
              data-testid="raw-score-marker"
            />
          </div>
          <div className="flex items-center justify-between text-[10px] text-gray-500 font-mono">
            <span>SELL {sellThreshold.toFixed(1)}</span>
            <span className="text-gray-300 text-xs font-semibold">
              {rawScore.toFixed(3)}
            </span>
            <span>BUY +{buyThreshold.toFixed(1)}</span>
          </div>
        </div>

        {/* Consensus score */}
        <div className="flex items-center justify-between rounded-lg bg-gray-800/40 px-3 py-2">
          <span className="text-xs text-gray-500 uppercase tracking-wider">
            Consensus
          </span>
          <span className="text-sm font-semibold text-gray-200 font-mono">
            {consensusScore.toFixed(3)}
          </span>
        </div>
      </div>
    </div>
  );
}
