const regimeStyles: Record<string, string> = {
  bull: "bg-green-400/20 text-green-400",
  bear: "bg-red-400/20 text-red-400",
  sideways: "bg-gray-400/20 text-gray-400",
  high_volatility: "bg-amber-400/20 text-amber-400",
  risk_off: "bg-purple-400/20 text-purple-400",
};

function formatRegime(regime: string): string {
  return regime
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface RegimeBadgeProps {
  regime: string;
  className?: string;
}

export default function RegimeBadge({ regime, className = "" }: RegimeBadgeProps) {
  const style = regimeStyles[regime.toLowerCase()] ?? "bg-gray-700 text-gray-300";
  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-medium ${style} ${className}`}
    >
      {formatRegime(regime)}
    </span>
  );
}
