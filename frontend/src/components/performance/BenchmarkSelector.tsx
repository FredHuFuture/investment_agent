import type { BenchmarkSymbol } from "../../api/types";
import { BENCHMARK_OPTIONS } from "../../api/endpoints";

interface Props {
  value: BenchmarkSymbol;
  onChange: (value: BenchmarkSymbol) => void;
}

export default function BenchmarkSelector({ value, onChange }: Props) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <label htmlFor="benchmark-selector" className="text-gray-500 uppercase tracking-wider">
        Benchmark
      </label>
      <select
        id="benchmark-selector"
        data-testid="benchmark-selector"
        value={value}
        onChange={(e) => onChange(e.target.value as BenchmarkSymbol)}
        className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-white"
      >
        {BENCHMARK_OPTIONS.map((sym) => (
          <option key={sym} value={sym}>{sym}</option>
        ))}
      </select>
    </div>
  );
}
