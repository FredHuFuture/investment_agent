import type { TradeAnnotation } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";

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

interface LessonSummaryProps {
  annotations: TradeAnnotation[];
}

export default function LessonSummary({ annotations }: LessonSummaryProps) {
  // Count lesson tags
  const tagCounts = new Map<string, number>();
  for (const a of annotations) {
    if (a.lesson_tag) {
      tagCounts.set(a.lesson_tag, (tagCounts.get(a.lesson_tag) ?? 0) + 1);
    }
  }

  // Sort by count descending
  const sorted = [...tagCounts.entries()].sort((a, b) => b[1] - a[1]);
  const top3 = sorted.slice(0, 3);
  const totalTagged = sorted.reduce((sum, [, count]) => sum + count, 0);

  if (annotations.length === 0) {
    return (
      <Card>
        <CardHeader title="Lesson Summary" />
        <CardBody>
          <p className="text-gray-500 text-sm text-center py-2">
            No annotations yet. Add notes to your closed trades to track lessons learned.
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Lesson Summary"
        subtitle={`${annotations.length} annotation${annotations.length !== 1 ? "s" : ""}, ${totalTagged} tagged`}
      />
      <CardBody>
        {/* Top lessons */}
        {top3.length > 0 && (
          <div className="mb-4">
            <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-2">
              Top Lessons
            </div>
            <div className="space-y-1.5">
              {top3.map(([tag, count], i) => (
                <div key={tag} className="flex items-center gap-2">
                  <span className="text-gray-500 text-xs font-mono w-4">
                    {i + 1}.
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full border ${LESSON_TAG_COLORS[tag] ?? "bg-gray-600/20 text-gray-400 border-gray-600/30"}`}
                  >
                    {formatLessonTag(tag)}
                  </span>
                  <span className="text-gray-400 text-xs font-mono">
                    {count}x
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* All tags as pills */}
        {sorted.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-2">
              All Tags
            </div>
            <div className="flex flex-wrap gap-2">
              {sorted.map(([tag, count]) => (
                <span
                  key={tag}
                  className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${LESSON_TAG_COLORS[tag] ?? "bg-gray-600/20 text-gray-400 border-gray-600/30"}`}
                >
                  {formatLessonTag(tag)}
                  <span className="font-mono opacity-70">{count}</span>
                </span>
              ))}
            </div>
          </div>
        )}

        {sorted.length === 0 && (
          <p className="text-gray-500 text-sm text-center py-2">
            No lesson tags assigned yet. Tag your annotations to see patterns.
          </p>
        )}
      </CardBody>
    </Card>
  );
}
