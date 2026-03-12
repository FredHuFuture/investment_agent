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
  const borderColor =
    trend === "up"
      ? "border-l-green-500/60"
      : trend === "down"
        ? "border-l-red-500/60"
        : "border-l-transparent";

  const valueColor =
    trend === "up"
      ? "text-green-400"
      : trend === "down"
        ? "text-red-400"
        : "text-white";

  return (
    <div
      className={`rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 border-l-2 ${borderColor} p-5 min-w-0`}
    >
      <div className="text-[11px] font-medium uppercase tracking-wider text-gray-500">
        {label}
      </div>
      <div
        className={`mt-1.5 text-2xl sm:text-3xl font-bold ${className ?? valueColor}`}
      >
        {value}
      </div>
      {sub && (
        <div
          className={`mt-1 text-xs ${className ? className : trend === "up" ? "text-green-500/70" : trend === "down" ? "text-red-500/70" : "text-gray-500"}`}
        >
          {sub}
        </div>
      )}
    </div>
  );
}
