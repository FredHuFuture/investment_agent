export default function MetricCard({
  label,
  value,
  sub,
  className,
  trend,
}: {
  label: string;
  value: string;
  sub?: string;
  className?: string;
  /** "up" = green accent, "down" = red accent, undefined = neutral */
  trend?: "up" | "down";
}) {
  const valueColor =
    trend === "up"
      ? "text-up"
      : trend === "down"
        ? "text-down"
        : "text-gray-100";

  const subColor =
    trend === "up"
      ? "text-up/70"
      : trend === "down"
        ? "text-down/70"
        : "text-gray-500";

  return (
    <div className="rounded-card bg-gray-900 border border-gray-800/60 shadow-card p-4 sm:p-5 min-w-0">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
        {label}
      </div>
      <div
        className={`mt-1.5 font-display text-2xl sm:text-3xl font-semibold tracking-tight ${className ?? valueColor}`}
      >
        {value}
      </div>
      {sub && (
        <div
          className={`mt-1 text-xs font-medium ${className ? className : subColor}`}
        >
          {sub}
        </div>
      )}
    </div>
  );
}
