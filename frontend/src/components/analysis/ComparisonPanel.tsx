import { useState, useCallback } from "react";
import type { AnalysisResult } from "../../api/types";
import { analyzeTicker } from "../../api/endpoints";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { TextInput } from "../ui/Input";
import { useToast } from "../../contexts/ToastContext";
import ComparisonResultRow from "./ComparisonResultRow";

interface TickerEntry {
  ticker: string;
  assetType: "stock" | "crypto";
}

const MAX_TICKERS = 5;
const MIN_TICKERS = 2;

function emptyEntry(): TickerEntry {
  return { ticker: "", assetType: "stock" };
}

export default function ComparisonPanel() {
  const { toast } = useToast();

  const [entries, setEntries] = useState<TickerEntry[]>([
    emptyEntry(),
    emptyEntry(),
  ]);
  const [results, setResults] = useState<Record<string, AnalysisResult>>({});
  const [loading, setLoading] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<Record<string, string>>({});

  const updateEntry = useCallback(
    (index: number, patch: Partial<TickerEntry>) => {
      setEntries((prev) => {
        const next = [...prev];
        next[index] = { ...next[index]!, ...patch };
        return next;
      });
    },
    [],
  );

  const addTicker = useCallback(() => {
    setEntries((prev) => {
      if (prev.length >= MAX_TICKERS) return prev;
      return [...prev, emptyEntry()];
    });
  }, []);

  const removeTicker = useCallback((index: number) => {
    setEntries((prev) => {
      if (prev.length <= MIN_TICKERS) return prev;
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  const toggleAssetType = useCallback(
    (index: number) => {
      const current = entries[index]!.assetType;
      updateEntry(index, {
        assetType: current === "stock" ? "crypto" : "stock",
      });
    },
    [entries, updateEntry],
  );

  const analyzeAll = useCallback(async () => {
    // Collect valid tickers
    const validEntries = entries.filter((e) => e.ticker.trim().length > 0);
    if (validEntries.length < 2) {
      toast.warning(
        "Need at least 2 tickers",
        "Enter at least 2 ticker symbols to compare.",
      );
      return;
    }

    const tickerKeys = validEntries.map((e) => e.ticker.trim().toUpperCase());

    // Mark all as loading
    setLoading(new Set(tickerKeys));
    setErrors({});

    const promises = validEntries.map(async (entry) => {
      const key = entry.ticker.trim().toUpperCase();
      try {
        const res = await analyzeTicker(key, entry.assetType);
        return { key, data: res.data, error: null };
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Analysis failed";
        return { key, data: null, error: msg };
      }
    });

    const settled = await Promise.allSettled(promises);

    const newResults: Record<string, AnalysisResult> = { ...results };
    const newErrors: Record<string, string> = {};
    let errorCount = 0;

    for (const outcome of settled) {
      if (outcome.status === "fulfilled") {
        const { key, data, error } = outcome.value;
        if (data) {
          newResults[key] = data;
        }
        if (error) {
          newErrors[key] = error;
          errorCount++;
        }
      } else {
        // Should not happen with our wrapping, but handle gracefully
        errorCount++;
      }
    }

    setResults(newResults);
    setErrors(newErrors);
    setLoading(new Set());

    if (errorCount > 0) {
      toast.error(
        "Some analyses failed",
        `${errorCount} ticker(s) could not be analyzed.`,
      );
    }
  }, [entries, results, toast]);

  const isAnyLoading = loading.size > 0;

  // Normalized ticker list for result display
  const tickerKeys = entries
    .map((e) => e.ticker.trim().toUpperCase())
    .filter((t) => t.length > 0);

  const hasResults = tickerKeys.some((t) => results[t] !== undefined);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Compare Tickers"
          subtitle="Analyze 2-5 tickers side-by-side"
        />
        <CardBody>
          <div className="space-y-3">
            {entries.map((entry, idx) => (
              <div key={idx} className="flex items-end gap-2">
                <TextInput
                  label={idx === 0 ? "Ticker" : undefined}
                  value={entry.ticker}
                  onChange={(e) =>
                    updateEntry(idx, { ticker: e.target.value })
                  }
                  placeholder={`Ticker ${idx + 1}`}
                  className="w-32"
                  disabled={isAnyLoading}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleAssetType(idx)}
                  disabled={isAnyLoading}
                  title="Toggle asset type"
                >
                  {entry.assetType === "stock" ? "Stock" : "Crypto"}
                </Button>
                {entries.length > MIN_TICKERS && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeTicker(idx)}
                    disabled={isAnyLoading}
                    aria-label={`Remove ticker ${idx + 1}`}
                  >
                    &times;
                  </Button>
                )}
                {errors[entry.ticker.trim().toUpperCase()] && (
                  <span className="text-red-400 text-xs">
                    {errors[entry.ticker.trim().toUpperCase()]}
                  </span>
                )}
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3 mt-4 pt-3 border-t border-gray-800">
            {entries.length < MAX_TICKERS && (
              <Button
                variant="ghost"
                size="sm"
                onClick={addTicker}
                disabled={isAnyLoading}
              >
                + Add Ticker
              </Button>
            )}
            <Button
              onClick={analyzeAll}
              loading={isAnyLoading}
              disabled={isAnyLoading}
            >
              Analyze All
            </Button>
          </div>
        </CardBody>
      </Card>

      {hasResults && (
        <ComparisonResultRow results={results} tickers={tickerKeys} />
      )}
    </div>
  );
}
