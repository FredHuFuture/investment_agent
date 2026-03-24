import { useState } from "react";
import { TextInput } from "../ui/Input";
import { Button } from "../ui/Button";
import { updateThesis } from "../../api/endpoints";
import { useToast } from "../../contexts/ToastContext";

interface ThesisEditFormProps {
  ticker: string;
  initialValues: {
    thesis_text: string | null;
    target_price: number | null;
    stop_loss: number | null;
    expected_hold_days: number | null;
    expected_return_pct: number | null;
  };
  onSaved: () => void;
  onCancel: () => void;
}

export default function ThesisEditForm({
  ticker,
  initialValues,
  onSaved,
  onCancel,
}: ThesisEditFormProps) {
  const { toast } = useToast();

  const [thesisText, setThesisText] = useState(initialValues.thesis_text ?? "");
  const [targetPrice, setTargetPrice] = useState(
    initialValues.target_price != null ? String(initialValues.target_price) : "",
  );
  const [stopLoss, setStopLoss] = useState(
    initialValues.stop_loss != null ? String(initialValues.stop_loss) : "",
  );
  const [expectedHoldDays, setExpectedHoldDays] = useState(
    initialValues.expected_hold_days != null
      ? String(initialValues.expected_hold_days)
      : "",
  );
  const [expectedReturnPct, setExpectedReturnPct] = useState(
    initialValues.expected_return_pct != null
      ? String(initialValues.expected_return_pct * 100)
      : "",
  );
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await updateThesis(ticker, {
        thesis_text: thesisText.trim() || null,
        target_price: targetPrice ? parseFloat(targetPrice) : null,
        stop_loss: stopLoss ? parseFloat(stopLoss) : null,
        expected_hold_days: expectedHoldDays
          ? parseInt(expectedHoldDays, 10)
          : null,
        expected_return_pct: expectedReturnPct
          ? parseFloat(expectedReturnPct) / 100
          : null,
      });
      toast.success("Thesis updated", `Thesis for ${ticker} saved successfully.`);
      onSaved();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to update thesis";
      toast.error("Update failed", message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Thesis text */}
      <div>
        <label
          htmlFor="thesis-text"
          className="block text-sm font-medium text-gray-300 mb-1.5"
        >
          Thesis
        </label>
        <textarea
          id="thesis-text"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-gray-100 placeholder:text-gray-500 focus:ring-2 focus:ring-accent focus:border-accent outline-none transition-colors duration-150"
          rows={3}
          value={thesisText}
          onChange={(e) => setThesisText(e.target.value)}
          placeholder="Why did you enter this position?"
        />
      </div>

      {/* Numeric fields */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <TextInput
          label="Target Price"
          type="number"
          step="any"
          value={targetPrice}
          onChange={(e) => setTargetPrice(e.target.value)}
          placeholder="220"
        />
        <TextInput
          label="Stop Loss"
          type="number"
          step="any"
          value={stopLoss}
          onChange={(e) => setStopLoss(e.target.value)}
          placeholder="170"
        />
        <TextInput
          label="Expected Hold Days"
          type="number"
          step="1"
          value={expectedHoldDays}
          onChange={(e) => setExpectedHoldDays(e.target.value)}
          placeholder="60"
        />
        <TextInput
          label="Expected Return %"
          type="number"
          step="any"
          value={expectedReturnPct}
          onChange={(e) => setExpectedReturnPct(e.target.value)}
          placeholder="18"
          hint="As percentage (e.g. 18 for 18%)"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-1">
        <Button type="submit" size="sm" loading={saving}>
          Save Thesis
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onCancel}
          disabled={saving}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}
