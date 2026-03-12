import { signalBg } from "../../lib/colors";

export default function SignalBadge({ signal }: { signal: string }) {
  const cls = signalBg[signal.toUpperCase()] ?? "bg-gray-700 text-gray-300";
  return (
    <span
      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${cls}`}
    >
      {signal.toUpperCase()}
    </span>
  );
}
