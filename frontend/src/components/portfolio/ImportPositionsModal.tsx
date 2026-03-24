import { useState, useRef, useCallback } from "react";
import { Button } from "../ui/Button";
import { bulkImportPositions } from "../../api/endpoints";
import type { BulkImportResult } from "../../api/types";
import { useToast } from "../../contexts/ToastContext";

interface ParsedRow {
  ticker: string;
  quantity: number;
  avg_cost: number;
  entry_date: string;
  asset_type?: string;
  sector?: string;
}

interface ParseError {
  line: number;
  text: string;
  reason: string;
}

interface ImportPositionsModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const EXAMPLE_CSV = `ticker,quantity,avg_cost,entry_date
AAPL,10,175.50,2024-06-15
MSFT,5,420.00,2024-07-01
GOOGL,8,178.25,2024-08-10`;

function parseCSV(text: string): { rows: ParsedRow[]; errors: ParseError[] } {
  const lines = text
    .trim()
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  if (lines.length === 0) return { rows: [], errors: [] };

  const rows: ParsedRow[] = [];
  const errors: ParseError[] = [];
  let startIdx = 0;

  // Detect header row
  const firstLine = lines[0] ?? "";
  if (firstLine.toLowerCase().includes("ticker") || firstLine.toLowerCase().includes("symbol")) {
    startIdx = 1;
  }

  for (let i = startIdx; i < lines.length; i++) {
    const line = lines[i] ?? "";
    const parts = line.split(",").map((p) => p.trim());
    if (parts.length < 4) {
      errors.push({
        line: i + 1,
        text: line,
        reason: "Expected at least 4 fields: ticker, quantity, avg_cost, entry_date",
      });
      continue;
    }

    const ticker = parts[0] ?? "";
    const qtyStr = parts[1] ?? "";
    const costStr = parts[2] ?? "";
    const entryDate = parts[3] ?? "";
    const assetType = parts[4] ?? "";
    const sector = parts[5] ?? "";
    const quantity = parseFloat(qtyStr);
    const avg_cost = parseFloat(costStr);

    if (!ticker || ticker.length === 0) {
      errors.push({ line: i + 1, text: line, reason: "Missing ticker" });
      continue;
    }
    if (isNaN(quantity) || quantity <= 0) {
      errors.push({ line: i + 1, text: line, reason: "Invalid or non-positive quantity" });
      continue;
    }
    if (isNaN(avg_cost) || avg_cost <= 0) {
      errors.push({ line: i + 1, text: line, reason: "Invalid or non-positive avg_cost" });
      continue;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(entryDate)) {
      errors.push({ line: i + 1, text: line, reason: "Invalid date format (expected YYYY-MM-DD)" });
      continue;
    }

    const row: ParsedRow = {
      ticker: ticker.toUpperCase(),
      quantity,
      avg_cost,
      entry_date: entryDate,
    };
    if (assetType.length > 0) row.asset_type = assetType;
    if (sector.length > 0) row.sector = sector;

    rows.push(row);
  }

  return { rows, errors };
}

export default function ImportPositionsModal({
  open,
  onClose,
  onSuccess,
}: ImportPositionsModalProps) {
  const { toast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [csvText, setCsvText] = useState("");
  const [parsed, setParsed] = useState<ParsedRow[]>([]);
  const [parseErrors, setParseErrors] = useState<ParseError[]>([]);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<BulkImportResult | null>(null);
  const [step, setStep] = useState<"input" | "preview" | "result">("input");

  const reset = useCallback(() => {
    setCsvText("");
    setParsed([]);
    setParseErrors([]);
    setResult(null);
    setStep("input");
    setImporting(false);
  }, []);

  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  const handleParse = useCallback(() => {
    const { rows, errors } = parseCSV(csvText);
    setParsed(rows);
    setParseErrors(errors);
    if (rows.length > 0) {
      setStep("preview");
    } else {
      toast.error("No valid rows", "Please check your CSV format and try again.");
    }
  }, [csvText, toast]);

  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        const text = ev.target?.result as string;
        setCsvText(text);
      };
      reader.readAsText(file);
      // Reset file input so same file can be re-uploaded
      e.target.value = "";
    },
    [],
  );

  const handleImport = useCallback(async () => {
    if (parsed.length === 0) return;
    setImporting(true);
    try {
      const res = await bulkImportPositions(parsed);
      setResult(res.data);
      setStep("result");
      if (res.data.imported > 0) {
        toast.success(
          "Import complete",
          `${res.data.imported} position(s) imported, ${res.data.skipped} skipped`,
        );
        onSuccess();
      } else {
        toast.info(
          "Nothing imported",
          `${res.data.skipped} skipped, ${res.data.errors.length} error(s)`,
        );
      }
    } catch (err) {
      toast.error(
        "Import failed",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setImporting(false);
    }
  }, [parsed, toast, onSuccess]);

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
        aria-labelledby="import-modal-title"
        className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-xl bg-gray-900 border border-gray-700 p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 id="import-modal-title" className="text-lg font-semibold text-white">
            Import Positions from CSV
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
                CSV Format (one position per line):
              </p>
              <pre className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
                {EXAMPLE_CSV}
              </pre>
              <p className="text-xs text-gray-500 mt-2">
                Optional columns: asset_type (stock/btc/eth), sector
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Paste CSV data
              </label>
              <textarea
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-100 placeholder:text-gray-500 focus:ring-2 focus:ring-accent focus:border-accent outline-none font-mono text-sm"
                rows={8}
                value={csvText}
                onChange={(e) => setCsvText(e.target.value)}
                placeholder="AAPL,10,175.50,2024-06-15&#10;MSFT,5,420.00,2024-07-01"
              />
            </div>

            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">or</span>
              <Button
                variant="secondary"
                size="sm"
                type="button"
                onClick={() => fileRef.current?.click()}
              >
                Upload .csv file
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={handleFileUpload}
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button variant="secondary" type="button" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleParse}
                disabled={csvText.trim().length === 0}
              >
                Preview
              </Button>
            </div>
          </div>
        )}

        {step === "preview" && (
          <div className="space-y-4">
            {parseErrors.length > 0 && (
              <div className="rounded-lg bg-red-900/20 border border-red-800/50 p-3">
                <p className="text-sm font-medium text-red-400 mb-1">
                  {parseErrors.length} row(s) skipped due to errors:
                </p>
                <ul className="text-xs text-red-300 space-y-1">
                  {parseErrors.map((e, i) => (
                    <li key={i}>
                      Line {e.line}: {e.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="border-b border-gray-700 text-gray-400 text-xs">
                    <th className="py-2 px-3">Ticker</th>
                    <th className="py-2 px-3 text-right">Qty</th>
                    <th className="py-2 px-3 text-right">Avg Cost</th>
                    <th className="py-2 px-3">Entry Date</th>
                    <th className="py-2 px-3">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {parsed.map((row, i) => (
                    <tr
                      key={i}
                      className="border-b border-gray-800 text-gray-300"
                    >
                      <td className="py-2 px-3 font-medium">{row.ticker}</td>
                      <td className="py-2 px-3 text-right">{row.quantity}</td>
                      <td className="py-2 px-3 text-right">
                        ${row.avg_cost.toFixed(2)}
                      </td>
                      <td className="py-2 px-3">{row.entry_date}</td>
                      <td className="py-2 px-3 text-gray-500">
                        {row.asset_type ?? "stock"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-xs text-gray-500">
              {parsed.length} position(s) ready to import. Existing tickers will
              be skipped.
            </p>

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
                onClick={handleImport}
                loading={importing}
              >
                Import {parsed.length} Position{parsed.length !== 1 ? "s" : ""}
              </Button>
            </div>
          </div>
        )}

        {step === "result" && result && (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg bg-emerald-900/20 border border-emerald-800/50 p-3 text-center">
                <p className="text-2xl font-bold text-emerald-400">
                  {result.imported}
                </p>
                <p className="text-xs text-gray-400">Imported</p>
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
                Import More
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
