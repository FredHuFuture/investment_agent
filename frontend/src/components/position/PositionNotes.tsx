import { useState } from "react";
import { useApi } from "../../hooks/useApi";
import { getPositionNotes, addPositionNote } from "../../api/endpoints";
import type { PositionNote } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import { formatDate } from "../../lib/formatters";

interface PositionNotesProps {
  ticker: string;
}

export default function PositionNotes({ ticker }: PositionNotesProps) {
  const api = useApi<PositionNote[]>(
    () => getPositionNotes(ticker),
    [ticker],
  );

  const [noteText, setNoteText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleAdd() {
    const trimmed = noteText.trim();
    if (!trimmed) return;

    setSubmitting(true);
    try {
      await addPositionNote(ticker, { note_text: trimmed });
      setNoteText("");
      api.refetch();
    } catch {
      // silently fail; user can retry
    } finally {
      setSubmitting(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !submitting) {
      handleAdd();
    }
  }

  if (api.loading && !api.data) {
    return (
      <Card>
        <CardHeader title="Quick Notes" />
        <CardBody>
          <Skeleton className="h-4 w-3/4 mb-2" />
          <Skeleton className="h-4 w-1/2" />
        </CardBody>
      </Card>
    );
  }

  if (api.error) {
    return (
      <Card>
        <CardHeader title="Quick Notes" />
        <CardBody>
          <p className="text-red-400 text-sm">{api.error}</p>
        </CardBody>
      </Card>
    );
  }

  const notes = api.data ?? [];

  return (
    <Card>
      <CardHeader title="Quick Notes" />
      <CardBody>
        {/* Add note input */}
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add a note..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-300 placeholder-gray-500 focus:outline-none focus:border-accent"
            disabled={submitting}
          />
          <button
            onClick={handleAdd}
            disabled={submitting || !noteText.trim()}
            className="px-3 py-1.5 bg-accent hover:bg-accent-dark disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded transition-colors"
          >
            Add
          </button>
        </div>

        {/* Notes list */}
        {notes.length === 0 ? (
          <p className="text-gray-500 text-sm">No notes yet.</p>
        ) : (
          <ul className="space-y-2">
            {notes.map((note) => (
              <li
                key={note.id}
                className="border-b border-gray-700 pb-2 last:border-b-0"
              >
                <p className="text-gray-300 text-sm">{note.note_text}</p>
                <p className="text-gray-500 text-xs mt-0.5">
                  {formatDate(note.created_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
