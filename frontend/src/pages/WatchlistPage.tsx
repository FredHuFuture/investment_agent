import { useEffect, useState, useCallback } from "react";
import {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  analyzeWatchlistTicker,
  analyzeAllWatchlist,
  updateWatchlistItem,
} from "../api/endpoints";
import type { WatchlistItem } from "../api/types";
import SignalBadge from "../components/shared/SignalBadge";
import { usePageTitle } from "../hooks/usePageTitle";
import { Card } from "../components/ui/Card";
import { TextInput, SelectInput } from "../components/ui/Input";
import { Button } from "../components/ui/Button";
import { SkeletonTable } from "../components/ui/Skeleton";
import { useToast } from "../contexts/ToastContext";
import ConfirmModal from "../components/ui/ConfirmModal";

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

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await getWatchlist();
      setItems(res.data);
    } catch (err) {
      toast.error("Failed to load watchlist", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

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
      toast.error("Failed to add", err instanceof Error ? err.message : "Unknown error");
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
      await fetchWatchlist();
    } catch (err) {
      toast.error("Failed to remove", err instanceof Error ? err.message : "Unknown error");
    }
  }

  async function handleAnalyze(t: string) {
    setAnalyzingTicker(t);
    try {
      await analyzeWatchlistTicker(t);
      toast.success("Analysis complete", t);
      await fetchWatchlist();
    } catch (err) {
      toast.error("Analysis failed", err instanceof Error ? err.message : "Unknown error");
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
      toast.success("Batch complete", `${res.data.success_count}/${res.data.total} succeeded`);
      await fetchWatchlist();
    } catch (err) {
      toast.error("Batch analysis failed", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setAnalyzingAll(false);
    }
  }

  function startEdit(item: WatchlistItem) {
    setEditingTicker(item.ticker);
    setEditForm({
      notes: item.notes || "",
      target_buy_price: item.target_buy_price != null ? String(item.target_buy_price) : "",
      alert_below_price: item.alert_below_price != null ? String(item.alert_below_price) : "",
    });
  }

  async function handleSaveEdit() {
    if (!editingTicker) return;
    setSaving(true);
    try {
      await updateWatchlistItem(editingTicker, {
        notes: editForm.notes || undefined,
        target_buy_price: editForm.target_buy_price ? parseFloat(editForm.target_buy_price) : undefined,
        alert_below_price: editForm.alert_below_price ? parseFloat(editForm.alert_below_price) : undefined,
      });
      toast.success("Updated", `${editingTicker} watchlist entry saved`);
      setEditingTicker(null);
      await fetchWatchlist();
    } catch (err) {
      toast.error("Update failed", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }

  function handleCancelEdit() {
    setEditingTicker(null);
  }

  function relativeTime(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Watchlist</h1>

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
            <Button type="submit" size="sm" loading={adding} disabled={!ticker.trim()}>
              Add
            </Button>
          </div>
        </form>
      </Card>

      {/* Analyze All + Batch Result */}
      {items.length > 0 && (
        <div className="flex items-center gap-4">
          <Button variant="primary" loading={analyzingAll} onClick={handleAnalyzeAll}>
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
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800/50 text-xs text-gray-500 uppercase tracking-wider">
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
              {items.map((item) => {
                const isEditing = editingTicker === item.ticker;
                return (
                  <tr
                    key={item.id}
                    className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors"
                  >
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
                            setEditForm((f) => ({ ...f, target_buy_price: e.target.value }))
                          }
                          placeholder="Target price"
                          className="w-28"
                        />
                      ) : (
                        item.target_buy_price != null
                          ? `$${item.target_buy_price.toFixed(2)}`
                          : "-"
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-300">
                      {isEditing ? (
                        <TextInput
                          type="number"
                          step="0.01"
                          value={editForm.alert_below_price}
                          onChange={(e) =>
                            setEditForm((f) => ({ ...f, alert_below_price: e.target.value }))
                          }
                          placeholder="Alert price"
                          className="w-28"
                        />
                      ) : (
                        item.alert_below_price != null
                          ? `$${item.alert_below_price.toFixed(2)}`
                          : "-"
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
                        ? relativeTime(item.last_analysis_at)
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
                              onClick={handleSaveEdit}
                            >
                              Save
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={handleCancelEdit}
                            >
                              Cancel
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => startEdit(item)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              loading={analyzingTicker === item.ticker}
                              onClick={() => handleAnalyze(item.ticker)}
                            >
                              Analyze
                            </Button>
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => setConfirmRemove(item.ticker)}
                            >
                              Remove
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>

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
