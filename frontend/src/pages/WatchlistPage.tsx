import { useEffect, useState, useCallback, useMemo } from "react";
import {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  analyzeWatchlistTicker,
  analyzeAllWatchlist,
  updateWatchlistItem,
} from "../api/endpoints";
import type { WatchlistItem, AnalysisResult } from "../api/types";
import SignalBadge from "../components/shared/SignalBadge";
import { usePageTitle } from "../hooks/usePageTitle";
import { Card } from "../components/ui/Card";
import { TextInput, SelectInput } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { SkeletonTable } from "../components/ui/Skeleton";
import { useToast } from "../contexts/ToastContext";
import ConfirmModal from "../components/ui/ConfirmModal";
import { formatRelativeDate } from "../lib/formatters";
import InlineAnalysisPanel from "../components/watchlist/InlineAnalysisPanel";
import AlertConfigPanel from "../components/watchlist/AlertConfigPanel";
import SignalFilterBar, {
  type SignalFilter,
} from "../components/watchlist/SignalFilterBar";
import ComparisonTable from "../components/watchlist/ComparisonTable";

const MAX_COMPARE = 5;

export default function WatchlistPage() {
  usePageTitle("Watchlist");
  const { toast } = useToast();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Add form state
  const [ticker, setTicker] = useState("");
  const [assetType, setAssetType] = useState("stock");
  const [notes, setNotes] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [adding, setAdding] = useState(false);

  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);

  // Inline editing state
  const [editingTicker, setEditingTicker] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{
    notes: string;
    target_buy_price: string;
    alert_below_price: string;
  }>({ notes: "", target_buy_price: "", alert_below_price: "" });
  const [saving, setSaving] = useState(false);

  // Analyzing state
  const [analyzingTicker, setAnalyzingTicker] = useState<string | null>(null);
  const [analyzingAll, setAnalyzingAll] = useState(false);
  const [batchResult, setBatchResult] = useState<{
    total: number;
    success_count: number;
  } | null>(null);

  // --- Inline analysis results (Feature 1) ---
  const [analysisResults, setAnalysisResults] = useState<
    Record<string, AnalysisResult>
  >({});
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  // --- Signal filter (Feature 2) ---
  const [signalFilter, setSignalFilter] = useState<SignalFilter>("ALL");

  // --- Comparison mode (Feature 3) ---
  const [compareMode, setCompareMode] = useState(false);
  const [selectedTickers, setSelectedTickers] = useState<Set<string>>(
    new Set(),
  );

  // --- Alert config panel (Sprint 30) ---
  const [expandedAlertTicker, setExpandedAlertTicker] = useState<string | null>(
    null,
  );

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await getWatchlist();
      setItems(res.data);
    } catch (err) {
      toast.error(
        "Failed to load watchlist",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  // Filtered items based on signal filter
  const filteredItems = useMemo(() => {
    switch (signalFilter) {
      case "BUY":
        return items.filter(
          (i) => i.last_signal?.toUpperCase() === "BUY",
        );
      case "SELL":
        return items.filter(
          (i) => i.last_signal?.toUpperCase() === "SELL",
        );
      case "HOLD":
        return items.filter(
          (i) => i.last_signal?.toUpperCase() === "HOLD",
        );
      case "UNANALYZED":
        return items.filter((i) => !i.last_signal);
      default:
        return items;
    }
  }, [items, signalFilter]);

  // Items selected for comparison
  const comparedItems = useMemo(
    () => items.filter((i) => selectedTickers.has(i.ticker)),
    [items, selectedTickers],
  );

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!ticker.trim()) return;
    setAdding(true);
    try {
      await addToWatchlist({
        ticker: ticker.trim().toUpperCase(),
        asset_type: assetType,
        notes,
        target_buy_price: targetPrice ? parseFloat(targetPrice) : undefined,
      });
      toast.success("Added to watchlist", ticker.trim().toUpperCase());
      setTicker("");
      setNotes("");
      setTargetPrice("");
      await fetchWatchlist();
    } catch (err) {
      toast.error(
        "Failed to add",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setAdding(false);
    }
  }

  async function handleConfirmRemove() {
    if (!confirmRemove) return;
    try {
      await removeFromWatchlist(confirmRemove);
      toast.success("Removed", confirmRemove + " removed from watchlist");
      setConfirmRemove(null);
      // Clean up related state
      setSelectedTickers((prev) => {
        const next = new Set(prev);
        next.delete(confirmRemove);
        return next;
      });
      if (expandedTicker === confirmRemove) setExpandedTicker(null);
      await fetchWatchlist();
    } catch (err) {
      toast.error(
        "Failed to remove",
        err instanceof Error ? err.message : "Unknown error",
      );
    }
  }

  async function handleAnalyze(t: string) {
    setAnalyzingTicker(t);
    try {
      const res = await analyzeWatchlistTicker(t);
      // Store analysis result for inline display
      setAnalysisResults((prev) => ({
        ...prev,
        [t]: res.data.analysis,
      }));
      setExpandedTicker(t);
      toast.success("Analysis complete", t);
      await fetchWatchlist();
    } catch (err) {
      toast.error(
        "Analysis failed",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setAnalyzingTicker(null);
    }
  }

  async function handleAnalyzeAll() {
    setAnalyzingAll(true);
    setBatchResult(null);
    try {
      const res = await analyzeAllWatchlist();
      setBatchResult({
        total: res.data.total,
        success_count: res.data.success_count,
      });
      toast.success(
        "Batch complete",
        `${res.data.success_count}/${res.data.total} succeeded`,
      );
      await fetchWatchlist();
    } catch (err) {
      toast.error(
        "Batch analysis failed",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setAnalyzingAll(false);
    }
  }

  function startEdit(item: WatchlistItem) {
    setEditingTicker(item.ticker);
    setEditForm({
      notes: item.notes || "",
      target_buy_price:
        item.target_buy_price != null ? String(item.target_buy_price) : "",
      alert_below_price:
        item.alert_below_price != null ? String(item.alert_below_price) : "",
    });
  }

  async function handleSaveEdit() {
    if (!editingTicker) return;
    setSaving(true);
    try {
      await updateWatchlistItem(editingTicker, {
        notes: editForm.notes || undefined,
        target_buy_price: editForm.target_buy_price
          ? parseFloat(editForm.target_buy_price)
          : undefined,
        alert_below_price: editForm.alert_below_price
          ? parseFloat(editForm.alert_below_price)
          : undefined,
      });
      toast.success("Updated", `${editingTicker} watchlist entry saved`);
      setEditingTicker(null);
      await fetchWatchlist();
    } catch (err) {
      toast.error(
        "Update failed",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setSaving(false);
    }
  }

  function handleCancelEdit() {
    setEditingTicker(null);
  }

  function toggleCompareSelect(t: string) {
    setSelectedTickers((prev) => {
      const next = new Set(prev);
      if (next.has(t)) {
        next.delete(t);
      } else if (next.size < MAX_COMPARE) {
        next.add(t);
      }
      return next;
    });
  }

  function handleExitCompare() {
    setCompareMode(false);
    setSelectedTickers(new Set());
  }

  return (
    <div className="space-y-6">
      {/* Page header with Compare toggle */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Watchlist</h1>
        {items.length >= 2 && (
          <Button
            variant={compareMode ? "primary" : "ghost"}
            size="sm"
            onClick={() => {
              if (compareMode) {
                handleExitCompare();
              } else {
                setCompareMode(true);
              }
            }}
          >
            {compareMode ? "Exit Compare" : "Compare"}
          </Button>
        )}
      </div>

      {/* Add Form */}
      <Card padding="md">
        <form onSubmit={handleAdd}>
          <h2 className="text-sm font-semibold text-gray-300 mb-3">
            Add Ticker
          </h2>
          <div className="flex flex-wrap items-end gap-3">
            <TextInput
              label="Ticker"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="AAPL"
              className="w-28"
            />
            <SelectInput
              label="Type"
              value={assetType}
              onChange={(e) => setAssetType(e.target.value)}
              options={[
                { value: "stock", label: "Stock" },
                { value: "btc", label: "BTC" },
                { value: "eth", label: "ETH" },
              ]}
            />
            <TextInput
              label="Target Price"
              type="number"
              step="0.01"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
              placeholder="Optional"
              className="w-28"
            />
            <TextInput
              label="Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Why you're watching..."
              className="flex-1 min-w-[120px]"
            />
            <Button
              type="submit"
              size="sm"
              loading={adding}
              disabled={!ticker.trim()}
            >
              Add
            </Button>
          </div>
        </form>
      </Card>

      {/* Analyze All + Batch Result */}
      {items.length > 0 && (
        <div className="flex items-center gap-4">
          <Button
            variant="primary"
            loading={analyzingAll}
            onClick={handleAnalyzeAll}
          >
            Analyze All
          </Button>
          {batchResult && (
            <span className="text-sm text-gray-400">
              Completed: {batchResult.success_count}/{batchResult.total}{" "}
              succeeded
            </span>
          )}
        </div>
      )}

      {/* Watchlist Table */}
      <Card className="overflow-hidden">
        {loading ? (
          <SkeletonTable rows={4} columns={6} />
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">
            No tickers on your watchlist yet. Add one above.
          </div>
        ) : (
          <>
            {/* Signal Filter Bar (Feature 2) */}
            <SignalFilterBar
              active={signalFilter}
              onChange={setSignalFilter}
            />

            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800/50 text-xs text-gray-500 uppercase tracking-wider">
                  {compareMode && (
                    <th className="w-10 px-3 py-3">
                      <span className="sr-only">Select</span>
                    </th>
                  )}
                  <th className="text-left px-4 py-3">Ticker</th>
                  <th className="text-left px-4 py-3">Type</th>
                  <th className="text-left px-4 py-3">Target Price</th>
                  <th className="text-left px-4 py-3">Alert Price</th>
                  <th className="text-left px-4 py-3">Notes</th>
                  <th className="text-center px-4 py-3">Signal</th>
                  <th className="text-center px-4 py-3">Confidence</th>
                  <th className="text-right px-4 py-3">Last Analyzed</th>
                  <th className="text-right px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const isEditing = editingTicker === item.ticker;
                  const isExpanded = expandedTicker === item.ticker;
                  const hasAnalysis = !!analysisResults[item.ticker];
                  const colSpanCount = compareMode ? 10 : 9;

                  return (
                    <WatchlistRow
                      key={item.id}
                      item={item}
                      isEditing={isEditing}
                      isExpanded={isExpanded && hasAnalysis}
                      analysis={analysisResults[item.ticker] ?? null}
                      compareMode={compareMode}
                      isSelected={selectedTickers.has(item.ticker)}
                      maxSelected={selectedTickers.size >= MAX_COMPARE}
                      colSpanCount={colSpanCount}
                      analyzingTicker={analyzingTicker}
                      saving={saving}
                      editForm={editForm}
                      setEditForm={setEditForm}
                      onStartEdit={() => startEdit(item)}
                      onSaveEdit={handleSaveEdit}
                      onCancelEdit={handleCancelEdit}
                      onAnalyze={() => handleAnalyze(item.ticker)}
                      onRemove={() => setConfirmRemove(item.ticker)}
                      onToggleCompare={() => toggleCompareSelect(item.ticker)}
                      onClosePanel={() => setExpandedTicker(null)}
                      isAlertExpanded={expandedAlertTicker === item.ticker}
                      onToggleAlerts={() =>
                        setExpandedAlertTicker(
                          expandedAlertTicker === item.ticker
                            ? null
                            : item.ticker,
                        )
                      }
                      onCloseAlerts={() => setExpandedAlertTicker(null)}
                    />
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </Card>

      {/* Comparison Table (Feature 3) */}
      {compareMode && comparedItems.length >= 2 && (
        <ComparisonTable
          items={comparedItems}
          analysisResults={analysisResults}
          onClose={handleExitCompare}
        />
      )}

      <ConfirmModal
        open={confirmRemove !== null}
        onClose={() => setConfirmRemove(null)}
        onConfirm={handleConfirmRemove}
        title={`Remove ${confirmRemove}?`}
        description="This will remove the ticker from your watchlist. You can always add it back later."
        confirmLabel="Remove"
        variant="danger"
      />
    </div>
  );
}

// --------------------------------------------------------------------------
// Extracted row component to keep the main component readable
// --------------------------------------------------------------------------
interface WatchlistRowProps {
  item: WatchlistItem;
  isEditing: boolean;
  isExpanded: boolean;
  analysis: AnalysisResult | null;
  compareMode: boolean;
  isSelected: boolean;
  maxSelected: boolean;
  colSpanCount: number;
  analyzingTicker: string | null;
  saving: boolean;
  editForm: { notes: string; target_buy_price: string; alert_below_price: string };
  setEditForm: React.Dispatch<
    React.SetStateAction<{
      notes: string;
      target_buy_price: string;
      alert_below_price: string;
    }>
  >;
  onStartEdit: () => void;
  onSaveEdit: () => void;
  onCancelEdit: () => void;
  onAnalyze: () => void;
  onRemove: () => void;
  onToggleCompare: () => void;
  onClosePanel: () => void;
  isAlertExpanded: boolean;
  onToggleAlerts: () => void;
  onCloseAlerts: () => void;
}

function WatchlistRow({
  item,
  isEditing,
  isExpanded,
  analysis,
  compareMode,
  isSelected,
  maxSelected,
  analyzingTicker,
  saving,
  editForm,
  setEditForm,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onAnalyze,
  onRemove,
  onToggleCompare,
  onClosePanel,
  isAlertExpanded,
  onToggleAlerts,
  onCloseAlerts,
}: WatchlistRowProps) {
  return (
    <>
      <tr className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors">
        {compareMode && (
          <td className="px-3 py-3 text-center">
            <input
              type="checkbox"
              checked={isSelected}
              disabled={!isSelected && maxSelected}
              onChange={onToggleCompare}
              className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500 focus:ring-offset-gray-900 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            />
          </td>
        )}
        <td className="px-4 py-3 font-mono font-bold text-white">
          {item.ticker}
        </td>
        <td className="px-4 py-3 text-gray-400">{item.asset_type}</td>
        <td className="px-4 py-3 text-gray-300">
          {isEditing ? (
            <TextInput
              type="number"
              step="0.01"
              value={editForm.target_buy_price}
              onChange={(e) =>
                setEditForm((f) => ({
                  ...f,
                  target_buy_price: e.target.value,
                }))
              }
              placeholder="Target price"
              className="w-28"
            />
          ) : item.target_buy_price != null ? (
            `$${item.target_buy_price.toFixed(2)}`
          ) : (
            "-"
          )}
        </td>
        <td className="px-4 py-3 text-gray-300">
          {isEditing ? (
            <TextInput
              type="number"
              step="0.01"
              value={editForm.alert_below_price}
              onChange={(e) =>
                setEditForm((f) => ({
                  ...f,
                  alert_below_price: e.target.value,
                }))
              }
              placeholder="Alert price"
              className="w-28"
            />
          ) : item.alert_below_price != null ? (
            `$${item.alert_below_price.toFixed(2)}`
          ) : (
            "-"
          )}
        </td>
        <td className="px-4 py-3 text-gray-400 max-w-[200px]">
          {isEditing ? (
            <TextInput
              value={editForm.notes}
              onChange={(e) =>
                setEditForm((f) => ({ ...f, notes: e.target.value }))
              }
              placeholder="Notes"
              className="w-full"
            />
          ) : (
            <span className="truncate block">{item.notes || "-"}</span>
          )}
        </td>
        <td className="px-4 py-3 text-center">
          {item.last_signal ? (
            <SignalBadge signal={item.last_signal} />
          ) : (
            <span className="text-gray-600">-</span>
          )}
        </td>
        <td className="px-4 py-3 text-center text-gray-300">
          {item.last_confidence != null
            ? `${item.last_confidence.toFixed(1)}%`
            : "-"}
        </td>
        <td className="px-4 py-3 text-right text-gray-500 text-xs">
          {item.last_analysis_at
            ? formatRelativeDate(item.last_analysis_at)
            : "Never"}
        </td>
        <td className="px-4 py-3 text-right">
          <div className="flex items-center justify-end gap-2">
            {isEditing ? (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  loading={saving}
                  onClick={onSaveEdit}
                >
                  Save
                </Button>
                <Button variant="ghost" size="sm" onClick={onCancelEdit}>
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <button
                  onClick={onToggleAlerts}
                  className={`p-1.5 rounded-lg transition-colors ${
                    isAlertExpanded
                      ? "text-yellow-400 bg-yellow-400/10"
                      : "text-gray-500 hover:text-yellow-400 hover:bg-gray-800"
                  }`}
                  title="Alert settings"
                  aria-label={`Alert settings for ${item.ticker}`}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-4 h-4"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 2a6 6 0 00-6 6c0 1.887-.454 3.665-1.257 5.234a.75.75 0 00.515 1.076 32.91 32.91 0 003.256.508 3.5 3.5 0 006.972 0 32.903 32.903 0 003.256-.508.75.75 0 00.515-1.076A11.448 11.448 0 0116 8a6 6 0 00-6-6zM8.05 14.943a33.54 33.54 0 003.9 0 2 2 0 01-3.9 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
                <Button variant="ghost" size="sm" onClick={onStartEdit}>
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  loading={analyzingTicker === item.ticker}
                  onClick={onAnalyze}
                >
                  Analyze
                </Button>
                <Button variant="danger" size="sm" onClick={onRemove}>
                  Remove
                </Button>
              </>
            )}
          </div>
        </td>
      </tr>

      {/* Inline Analysis Panel (Feature 1) */}
      {isExpanded && analysis && (
        <InlineAnalysisPanel analysis={analysis} onClose={onClosePanel} />
      )}

      {/* Alert Config Panel (Sprint 30) */}
      {isAlertExpanded && (
        <AlertConfigPanel ticker={item.ticker} onClose={onCloseAlerts} />
      )}
    </>
  );
}
