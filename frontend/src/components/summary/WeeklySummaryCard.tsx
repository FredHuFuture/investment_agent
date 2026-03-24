import { useState, useEffect, useCallback } from "react";
import { getLatestSummary, generateSummary } from "../../api/endpoints";
import { ApiError } from "../../api/client";
import type { SummaryResponse } from "../../api/types";
import { Button } from "../ui/Button";

type CardState =
  | { kind: "loading" }
  | { kind: "no_key" }
  | { kind: "no_summary" }
  | { kind: "ready"; summary: SummaryResponse }
  | { kind: "error"; message: string };

/** Render basic markdown: **bold**, bullet lines, and paragraph breaks. */
function renderSummaryText(text: string) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] ?? "";
    const trimmed = line.trim();

    if (trimmed === "") {
      elements.push(<br key={`br-${i}`} />);
      continue;
    }

    // Bullet line
    const isBullet = /^[-*]\s+/.test(trimmed);
    const content = isBullet ? trimmed.replace(/^[-*]\s+/, "") : trimmed;

    // Replace **text** with <strong>
    const parts: React.ReactNode[] = [];
    const regex = /\*\*(.+?)\*\*/g;
    let lastIdx = 0;
    let match: RegExpExecArray | null;

    while ((match = regex.exec(content)) !== null) {
      if (match.index > lastIdx) {
        parts.push(content.slice(lastIdx, match.index));
      }
      parts.push(<strong key={`b-${i}-${match.index}`}>{match[1]}</strong>);
      lastIdx = regex.lastIndex;
    }
    if (lastIdx < content.length) {
      parts.push(content.slice(lastIdx));
    }

    if (isBullet) {
      elements.push(
        <div key={`li-${i}`} className="flex gap-2 ml-2">
          <span className="text-gray-500 shrink-0">&bull;</span>
          <span>{parts}</span>
        </div>,
      );
    } else {
      elements.push(<p key={`p-${i}`}>{parts}</p>);
    }
  }

  return <div className="space-y-1">{elements}</div>;
}

export default function WeeklySummaryCard() {
  const [state, setState] = useState<CardState>({ kind: "loading" });
  const [generating, setGenerating] = useState(false);

  const fetchLatest = useCallback(async () => {
    try {
      const res = await getLatestSummary();
      setState({ kind: "ready", summary: res.data });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 503) {
          setState({ kind: "no_key" });
        } else if (err.status === 404) {
          setState({ kind: "no_summary" });
        } else {
          setState({ kind: "error", message: err.message });
        }
      } else {
        setState({ kind: "error", message: String(err) });
      }
    }
  }, []);

  useEffect(() => {
    fetchLatest();
  }, [fetchLatest]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await generateSummary();
      setState({ kind: "ready", summary: res.data });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 503) {
          setState({ kind: "no_key" });
        } else {
          setState({ kind: "error", message: err.message });
        }
      } else {
        setState({ kind: "error", message: String(err) });
      }
    } finally {
      setGenerating(false);
    }
  };

  const formatTimestamp = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString();
  };

  return (
    <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-300">
          Weekly Summary
        </h2>
        {state.kind === "ready" && (
          <span className="text-xs text-gray-500">
            ${state.summary.cost_usd.toFixed(2)}
          </span>
        )}
      </div>

      {/* Loading initial fetch */}
      {state.kind === "loading" && (
        <div className="flex items-center justify-center py-6">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-600 border-t-accent-light" />
        </div>
      )}

      {/* No API key */}
      {state.kind === "no_key" && (
        <div className="rounded-lg bg-yellow-900/20 border border-yellow-700/30 px-3 py-2">
          <p className="text-sm text-yellow-400">
            Set ANTHROPIC_API_KEY to enable AI summaries
          </p>
        </div>
      )}

      {/* No summary yet */}
      {state.kind === "no_summary" && (
        <div className="space-y-3">
          <p className="text-sm text-gray-500">
            No summary yet. Click &ldquo;Generate&rdquo; to create one.
          </p>
          <Button variant="primary" size="sm" loading={generating} onClick={handleGenerate}>
            {generating ? "Generating..." : "Generate"}
          </Button>
        </div>
      )}

      {/* Error */}
      {state.kind === "error" && (
        <div className="space-y-3">
          <p className="text-sm text-red-400">{state.message}</p>
          <Button variant="primary" size="sm" loading={generating} onClick={handleGenerate}>
            Retry
          </Button>
        </div>
      )}

      {/* Summary ready */}
      {state.kind === "ready" && (
        <div className="space-y-3">
          <div className="text-gray-200 text-sm leading-relaxed">
            {renderSummaryText(state.summary.summary_text)}
          </div>
          <div className="flex items-center justify-between pt-1 border-t border-gray-800/50">
            <span className="text-xs text-gray-500">
              {formatTimestamp(state.summary.generated_at)}
            </span>
            <Button variant="primary" size="sm" loading={generating} onClick={handleGenerate}>
              {generating ? "Generating..." : "Regenerate"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
