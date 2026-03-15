import { useState, useCallback } from "react";
import { useApi } from "../../hooks/useApi";
import { getTradeAnnotations, createTradeAnnotation } from "../../api/endpoints";
import type { TradeAnnotation } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { TextInput, SelectInput } from "../ui/Input";
import { useToast } from "../../contexts/ToastContext";

const LESSON_TAG_OPTIONS = [
  { value: "", label: "-- No tag --" },
  { value: "entry_timing", label: "Entry Timing" },
  { value: "exit_timing", label: "Exit Timing" },
  { value: "position_sizing", label: "Position Sizing" },
  { value: "thesis_quality", label: "Thesis Quality" },
  { value: "risk_management", label: "Risk Management" },
  { value: "emotional", label: "Emotional" },
];

const LESSON_TAG_COLORS: Record<string, string> = {
  entry_timing: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  exit_timing: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  position_sizing: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  thesis_quality: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  risk_management: "bg-red-500/20 text-red-400 border-red-500/30",
  emotional: "bg-pink-500/20 text-pink-400 border-pink-500/30",
};

function formatLessonTag(tag: string): string {
  return tag
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatAnnotationDate(dateStr: string): string {
  try {
    const d = new Date(dateStr + "Z");
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

interface TradeAnnotationPanelProps {
  ticker: string;
}

export default function TradeAnnotationPanel({ ticker }: TradeAnnotationPanelProps) {
  const { toast } = useToast();
  const [annotationText, setAnnotationText] = useState("");
  const [lessonTag, setLessonTag] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const annotationsApi = useApi<TradeAnnotation[]>(
    () => getTradeAnnotations(ticker),
    [ticker],
    { cacheKey: `journal:annotations:${ticker}`, ttlMs: 30_000 },
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!annotationText.trim()) return;

      setSubmitting(true);
      try {
        await createTradeAnnotation(ticker, {
          annotation_text: annotationText.trim(),
          lesson_tag: lessonTag || undefined,
        });
        toast.success("Annotation added", `Note saved for ${ticker}`);
        setAnnotationText("");
        setLessonTag("");
        annotationsApi.refetch();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        toast.error("Failed to save annotation", message);
      } finally {
        setSubmitting(false);
      }
    },
    [annotationText, lessonTag, ticker, toast, annotationsApi],
  );

  const annotations = annotationsApi.data ?? [];

  return (
    <Card>
      <CardHeader
        title="Trade Annotations"
        subtitle={`${annotations.length} note${annotations.length !== 1 ? "s" : ""} for ${ticker}`}
      />
      <CardBody>
        {/* Add annotation form */}
        <form onSubmit={handleSubmit} className="space-y-3 mb-4">
          <TextInput
            label="Add a note"
            placeholder="What did you learn from this trade?"
            value={annotationText}
            onChange={(e) => setAnnotationText(e.target.value)}
          />
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <SelectInput
                label="Lesson Tag"
                options={LESSON_TAG_OPTIONS}
                value={lessonTag}
                onChange={(e) => setLessonTag(e.target.value)}
              />
            </div>
            <Button
              type="submit"
              size="md"
              loading={submitting}
              disabled={!annotationText.trim()}
            >
              Save
            </Button>
          </div>
        </form>

        {/* Existing annotations list */}
        {annotationsApi.loading && annotations.length === 0 && (
          <div className="text-gray-500 text-sm py-4 text-center">
            Loading annotations...
          </div>
        )}

        {!annotationsApi.loading && annotations.length === 0 && (
          <div className="text-gray-500 text-sm py-4 text-center">
            No annotations yet. Add your first note above.
          </div>
        )}

        {annotations.length > 0 && (
          <div className="space-y-2">
            {annotations.map((a) => (
              <div
                key={a.id}
                className="bg-gray-800/40 rounded-lg px-3 py-2.5 border border-gray-700/50"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-gray-300 text-sm leading-relaxed flex-1">
                    {a.annotation_text}
                  </p>
                  <span className="text-gray-600 text-xs whitespace-nowrap">
                    {formatAnnotationDate(a.created_at)}
                  </span>
                </div>
                {a.lesson_tag && (
                  <span
                    className={`inline-block mt-1.5 text-xs px-2 py-0.5 rounded-full border ${LESSON_TAG_COLORS[a.lesson_tag] ?? "bg-gray-600/20 text-gray-400 border-gray-600/30"}`}
                  >
                    {formatLessonTag(a.lesson_tag)}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
