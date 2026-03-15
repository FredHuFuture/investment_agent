import { Button } from "../ui/Button";

export type SignalFilter = "ALL" | "BUY" | "SELL" | "HOLD" | "UNANALYZED";

const FILTERS: { value: SignalFilter; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "BUY", label: "BUY" },
  { value: "SELL", label: "SELL" },
  { value: "HOLD", label: "HOLD" },
  { value: "UNANALYZED", label: "Unanalyzed" },
];

interface SignalFilterBarProps {
  active: SignalFilter;
  onChange: (filter: SignalFilter) => void;
}

export default function SignalFilterBar({
  active,
  onChange,
}: SignalFilterBarProps) {
  return (
    <div className="flex items-center gap-1.5 px-4 py-2 border-b border-gray-800/50">
      {FILTERS.map((f) => (
        <Button
          key={f.value}
          variant={active === f.value ? "primary" : "ghost"}
          size="sm"
          className="!min-h-[28px] !px-2.5 !py-0.5 !text-xs !rounded-full"
          onClick={() => onChange(f.value)}
        >
          {f.label}
        </Button>
      ))}
    </div>
  );
}
