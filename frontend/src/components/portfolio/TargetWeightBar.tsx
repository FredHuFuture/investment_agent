interface TargetWeightBarProps {
  /** Actual portfolio weight as a fraction (0.0-1.0) */
  actualWeight: number;
  /** Target portfolio weight as a fraction (0.0-1.0); null hides the bar */
  targetWeight: number | null;
  /** Optional ticker for data-testid scoping */
  ticker?: string;
}

/**
 * Horizontal deviation bar showing actual vs target portfolio weight.
 * Returns null when targetWeight is null (no target set).
 *
 * Overweight (actual > target) → amber fill extends right from center
 * Underweight (actual < target) → green fill extends left from center
 *
 * Fill width scales 4x: a 25% deviation point spread fills the bar fully.
 */
export default function TargetWeightBar({
  actualWeight,
  targetWeight,
  ticker,
}: TargetWeightBarProps) {
  if (targetWeight === null || targetWeight === undefined) return null;

  const deviation = actualWeight - targetWeight; // +ve = overweight
  const absPctPts = Math.abs(deviation * 100);
  const isOver = deviation > 0.0001;
  const isUnder = deviation < -0.0001;

  // Fill scales 4x: 25% deviation saturates the bar
  const fillWidth = `${Math.min(absPctPts * 4, 100).toFixed(1)}%`;

  const fillColor = isOver
    ? "bg-amber-500/70"
    : isUnder
      ? "bg-green-500/70"
      : "bg-gray-600/50";
  const labelColor = isOver
    ? "text-amber-400"
    : isUnder
      ? "text-green-400"
      : "text-gray-400";
  const arrow = isOver ? "\u25b2" : isUnder ? "\u25bc" : "";

  return (
    <div
      data-testid={ticker ? `target-weight-bar-${ticker}` : "target-weight-bar"}
      className="flex items-center gap-2 text-xs"
    >
      <span className="text-gray-500 w-14 text-right font-mono">
        {(actualWeight * 100).toFixed(1)}%
      </span>
      <div className="relative h-2 w-24 bg-gray-800 rounded-full overflow-hidden">
        {/* center tick (target line) */}
        <div className="absolute left-1/2 inset-y-0 w-px bg-gray-500" />
        {/* deviation fill */}
        <div
          className={`absolute inset-y-0 ${fillColor} rounded-full`}
          style={{
            width: fillWidth,
            ...(isOver ? { left: "50%" } : { right: "50%" }),
          }}
        />
      </div>
      <span className={`w-12 font-mono ${labelColor}`}>
        {arrow}
        {deviation >= 0 ? "+" : ""}
        {(deviation * 100).toFixed(1)}%
      </span>
      <span className="text-gray-500 text-[10px]">
        (target {(targetWeight * 100).toFixed(1)}%)
      </span>
    </div>
  );
}
