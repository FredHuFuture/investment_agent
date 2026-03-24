import { useState, useEffect } from "react";
import type { WatchlistAlertConfig } from "../../api/types";
import {
  setWatchlistAlertConfig,
  getWatchlistAlertConfigs,
} from "../../api/endpoints";
import { Button } from "../ui/Button";
import { TextInput } from "../ui/Input";
import { useToast } from "../../contexts/ToastContext";

interface AlertConfigPanelProps {
  ticker: string;
  onClose: () => void;
}

export default function AlertConfigPanel({
  ticker,
  onClose,
}: AlertConfigPanelProps) {
  const { toast } = useToast();

  const [alertOnSignalChange, setAlertOnSignalChange] = useState(true);
  const [minConfidence, setMinConfidence] = useState("60");
  const [alertOnPriceBelow, setAlertOnPriceBelow] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // Load existing config on mount
  useEffect(() => {
    let cancelled = false;
    async function loadConfig() {
      try {
        const res = await getWatchlistAlertConfigs();
        if (cancelled) return;
        const existing = res.data.find(
          (c: WatchlistAlertConfig) => c.ticker === ticker,
        );
        if (existing) {
          setAlertOnSignalChange(existing.alert_on_signal_change);
          setMinConfidence(String(existing.min_confidence));
          setAlertOnPriceBelow(
            existing.alert_on_price_below != null
              ? String(existing.alert_on_price_below)
              : "",
          );
          setEnabled(existing.enabled);
        }
      } catch {
        // Silently use defaults if config load fails
      } finally {
        if (!cancelled) setLoaded(true);
      }
    }
    loadConfig();
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  async function handleSave() {
    setSaving(true);
    try {
      await setWatchlistAlertConfig(ticker, {
        alert_on_signal_change: alertOnSignalChange,
        min_confidence: parseFloat(minConfidence) || 60,
        alert_on_price_below: alertOnPriceBelow
          ? parseFloat(alertOnPriceBelow)
          : null,
        enabled,
      });
      toast.success("Alert config saved", `Alerts updated for ${ticker}`);
      onClose();
    } catch (err) {
      toast.error(
        "Failed to save alert config",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) {
    return (
      <tr>
        <td colSpan={10} className="px-4 py-0">
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 my-2">
            <span className="text-sm text-gray-400">Loading alert config...</span>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr>
      <td colSpan={10} className="px-4 py-0">
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 my-2">
          <div className="flex items-start justify-between gap-4 mb-3">
            <h3 className="text-sm font-semibold text-gray-200">
              Alert Settings &mdash; {ticker}
            </h3>
            <Button variant="ghost" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
            {/* Alert on signal change */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={alertOnSignalChange}
                onChange={(e) => setAlertOnSignalChange(e.target.checked)}
                className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-accent focus:ring-accent focus:ring-offset-gray-900 cursor-pointer"
              />
              <span className="text-sm text-gray-300">
                Alert on signal change
              </span>
            </label>

            {/* Min confidence */}
            <TextInput
              label="Min confidence (%)"
              type="number"
              step="1"
              min="0"
              max="100"
              value={minConfidence}
              onChange={(e) => setMinConfidence(e.target.value)}
              placeholder="60"
              className="w-28"
            />

            {/* Alert below price */}
            <TextInput
              label="Alert below price"
              type="number"
              step="0.01"
              value={alertOnPriceBelow}
              onChange={(e) => setAlertOnPriceBelow(e.target.value)}
              placeholder="Optional"
              className="w-28"
            />

            {/* Enabled toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-accent focus:ring-accent focus:ring-offset-gray-900 cursor-pointer"
              />
              <span className="text-sm text-gray-300">Enabled</span>
            </label>
          </div>

          <div className="mt-4 flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              loading={saving}
              onClick={handleSave}
            >
              Save
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </div>
      </td>
    </tr>
  );
}
