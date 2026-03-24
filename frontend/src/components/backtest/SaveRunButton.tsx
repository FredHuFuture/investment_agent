import { useState } from "react";
import { Button } from "../ui/Button";
import { useToast } from "../../contexts/ToastContext";
import { saveBacktestRun } from "../../lib/backtestStorage";
import type { BacktestResult } from "../../api/types";

interface Props {
  result: BacktestResult;
  ticker: string;
  params: { start_date: string; end_date: string; agents?: string[] };
  onSaved: () => void;
}

export default function SaveRunButton({ result, ticker, params, onSaved }: Props) {
  const [showInput, setShowInput] = useState(false);
  const [label, setLabel] = useState("");
  const [saved, setSaved] = useState(false);
  const { toast } = useToast();

  function handleSave() {
    saveBacktestRun(
      {
        ticker,
        label: label.trim() || "Untitled",
        params,
        metrics: result.metrics,
        equity_curve: result.equity_curve.map((p) => ({
          date: p.date,
          equity: p.equity,
        })),
      },
      label.trim() || undefined,
    );
    toast.success("Run saved", `${ticker} backtest saved to history`);
    setSaved(true);
    setShowInput(false);
    onSaved();
  }

  if (saved) {
    return (
      <div className="flex items-center gap-2 text-sm text-emerald-400">
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
        </svg>
        Saved to history
      </div>
    );
  }

  if (showInput) {
    return (
      <div className="flex items-center gap-2">
        <input
          type="text"
          placeholder="Label (optional)"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSave();
            if (e.key === "Escape") setShowInput(false);
          }}
          className="bg-gray-800/50 border border-gray-700/50 rounded-lg px-3 py-1.5 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-accent/50 w-48"
          autoFocus
        />
        <Button size="sm" onClick={handleSave}>
          Save
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setShowInput(false)}>
          Cancel
        </Button>
      </div>
    );
  }

  return (
    <Button size="sm" variant="secondary" onClick={() => setShowInput(true)}>
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0Z" />
      </svg>
      Save Result
    </Button>
  );
}
