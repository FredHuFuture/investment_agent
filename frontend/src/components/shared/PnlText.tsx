import { formatPct } from "../../lib/formatters";

export default function PnlText({ value }: { value: number }) {
  const color = value > 0 ? "text-green-400" : value < 0 ? "text-red-400" : "text-gray-400";
  return <span className={`font-mono ${color}`}>{formatPct(value)}</span>;
}
