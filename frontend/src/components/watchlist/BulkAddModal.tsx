import { useState, useCallback } from "react";
import { Button } from "../ui/Button";
import { bulkAddWatchlist } from "../../api/endpoints";
import type { BulkWatchlistResult } from "../../api/types";
import { useToast } from "../../contexts/ToastContext";

interface ParsedTicker {
  ticker: string;
  checked: boolean;
}

interface BulkAddModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

function parseTickers(text: string): ParsedTicker[] {
  const raw = text
    .split(/[,\n\r]+/)
    .map((t) => t.trim().toUpperCase())
    .filter((t) => t.length > 0 && /^[A-Z0-9.\-^]+$/.test(t));

  // Deduplicate
  const seen = new Set<string>();
  const result: ParsedTicker[] = [];
  for (const ticker of raw) {
    if (!seen.has(ticker)) {
      seen.add(ticker);
      result.push({ ticker, checked: true });
    }
  }
  return result;
}

export default function BulkAddModal({
  open,
  onClose,
  onSuccess,
}: BulkAddModalProps) {
  const { toast } = useToast();
  const [rawText, setRawText] = useState("");
  const [parsed, setParsed] = useState<ParsedTicker[]>([]);
  const [targetPrice, setTargetPrice] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<BulkWatchlistResult | null>(null);
  const [step, setStep] = useState<"input" | "preview" | "result">("input");

  const reset = useCallback(() => {
    setRawText("");
    setParsed([]);
    setTargetPrice("");
    setNotes("");
    setResult(null);
    setStep("input");
    setSubmitting(false);
  }, []);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  const handleParse = useCallback(() => {
    const items = parseTickers(rawText);
    setParsed(items);
    if (items.length > 0) {
      setStep("preview");
    } else {
      toast.error("No valid tickers", "Enter tickers separated by commas or newlines (e.g. AAPL, MSFT, NVDA).");
    }
  }, [rawText, toast]);

  const toggleTicker = useCallback((index: number) => {
    setParsed((prev) =>
      prev.map((item, i) =>
        i === index ? { ...item, checked: !item.checked } : item,
      ),
    );
  }, []);

  const toggleAll = useCallback(() => {
    setParsed((prev) => {
      const allChecked = prev.every((p) => p.checked);
      return prev.map((item) => ({ ...item, checked: !allChecked }));
    });
  }, []);

  const selectedCount = parsed.filter((p) => p.checked).length;

  const handleSubmit = useCallback(async () => {
    const selected = parsed.filter((p) => p.checked);
    if (selected.length === 0) return;
    setSubmitting(true);
    try {
      const payload = selected.map((p) => ({
        ticker: p.ticker,
        notes: notes || undefined,
        target_buy_price: targetPrice ? parseFloat(targetPrice) : undefined,
      }));
      const res = await bulkAddWatchlist(payload);
      setResult(res.data);
      setStep("result");
      if (res.data.added > 0) {
        toast.success(
          "Bulk add complete",
          `${res.data.added} ticker(s) added, ${res.data.skipped} skipped`,
        );
        onSuccess();
      } else {
        toast.info(
          "Nothing added",
          `${res.data.skipped} skipped, ${res.data.errors.length} error(s)`,
        );
      }
    } catch (err) {
      toast.error(
        "Bulk add failed",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setSubmitting(false);
    }
  }, [parsed, notes, targetPrice, toast, onSuccess]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="bulk-add-modal-title"
        className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-xl bg-gray-900 border border-gray-700 p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 id="bulk-add-modal-title" className="text-lg font-semibold text-white">
            Bulk Add to Watchlist
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {step === "input" && (
          <div className="space-y-4">
            <div className="rounded-lg bg-gray-800/50 border border-gray-700/50 p-3">
              <p className="text-xs text-gray-400 mb-1 font-medium">
                Enter tickers separated by commas or newlines:
              </p>
              <pre className="text-xs text-gray-300 font-mono">
                AAPL, MSFT, NVDA, GOOGL
              </pre>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Tickers
              </label>
              <textarea
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-100 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none font-mono text-sm"
                rows={5}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder="AAPL, MSFT, NVDA&#10;GOOGL&#10;AMZN, TSLA"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Target Buy Price (optional, shared)
                </label>
                <input
                  type="number"
                  step="0.01"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm"
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(e.target.value)}
                  placeholder="e.g. 150.00"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Notes (optional, shared)
                </label>
                <input
                  type="text"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 placeholder:text-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none text-sm"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Why you're watching..."
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="secondary" type="button" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleParse}
                disabled={rawText.trim().length === 0}
              >
                Preview
              </Button>
            </div>
          </div>
        )}

        {step === "preview" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-400">
                {selectedCount} of {parsed.length} ticker(s) selected
              </p>
              <button
                onClick={toggleAll}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
              >
                {parsed.every((p) => p.checked) ? "Deselect All" : "Select All"}
              </button>
            </div>

            <div className="max-h-60 overflow-y-auto rounded-lg bg-gray-800/50 border border-gray-700/50 divide-y divide-gray-800">
              {parsed.map((item, i) => (
                <label
                  key={item.ticker}
                  className="flex items-center gap-3 px-3 py-2 hover:bg-gray-800/80 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={item.checked}
                    onChange={() => toggleTicker(i)}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-900 cursor-pointer"
                  />
                  <span className="font-mono text-sm text-white font-medium">
                    {item.ticker}
                  </span>
                </label>
              ))}
            </div>

            {(notes || targetPrice) && (
              <div className="text-xs text-gray-500 space-y-1">
                {targetPrice && <p>Target Buy Price: ${parseFloat(targetPrice).toFixed(2)}</p>}
                {notes && <p>Notes: {notes}</p>}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="secondary"
                type="button"
                onClick={() => setStep("input")}
              >
                Back
              </Button>
              <Button
                type="button"
                onClick={handleSubmit}
                loading={submitting}
                disabled={selectedCount === 0}
              >
                Add {selectedCount} Ticker{selectedCount !== 1 ? "s" : ""}
              </Button>
            </div>
          </div>
        )}

        {step === "result" && result && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg bg-emerald-900/20 border border-emerald-800/50 p-3 text-center">
                <p className="text-2xl font-bold text-emerald-400">
                  {result.added}
                </p>
                <p className="text-xs text-gray-400">Added</p>
              </div>
              <div className="rounded-lg bg-yellow-900/20 border border-yellow-800/50 p-3 text-center">
                <p className="text-2xl font-bold text-yellow-400">
                  {result.skipped}
                </p>
                <p className="text-xs text-gray-400">Skipped</p>
              </div>
              <div className="rounded-lg bg-red-900/20 border border-red-800/50 p-3 text-center">
                <p className="text-2xl font-bold text-red-400">
                  {result.errors.length}
                </p>
                <p className="text-xs text-gray-400">Errors</p>
              </div>
            </div>

            {result.errors.length > 0 && (
              <div className="rounded-lg bg-red-900/20 border border-red-800/50 p-3">
                <p className="text-sm font-medium text-red-400 mb-1">Errors:</p>
                <ul className="text-xs text-red-300 space-y-1">
                  {result.errors.map((e, i) => (
                    <li key={i}>
                      {e.ticker}: {e.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="secondary" type="button" onClick={handleClose}>
                Close
              </Button>
              <Button type="button" onClick={reset}>
                Add More
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
