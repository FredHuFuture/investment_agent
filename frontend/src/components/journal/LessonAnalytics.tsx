import { useApi } from "../../hooks/useApi";
import { getLessonTagStats } from "../../api/endpoints";
import type { LessonTagStats } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import EmptyState from "../shared/EmptyState";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from "recharts";

function formatTag(tag: string): string {
  return tag
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export default function LessonAnalytics() {
  const { data, loading } = useApi<LessonTagStats[]>(
    () => getLessonTagStats(),
    { cacheKey: "journal:lesson-stats", ttlMs: 60_000 },
  );

  if (loading || !data) return null;
  if (data.length === 0) {
    return (
      <Card>
        <CardHeader title="Lesson Tag Analytics" />
        <CardBody>
          <EmptyState message="No lesson tag data yet. Tag your trade annotations to see analytics." />
        </CardBody>
      </Card>
    );
  }

  // Pattern alerts: tags with count >= 3 and win_rate < 30
  const patternAlerts = data.filter((s) => s.count >= 3 && s.win_rate < 30);

  // Prepare chart data (horizontal bar chart)
  const chartData = data.map((s) => ({
    tag: formatTag(s.tag),
    win_rate: s.win_rate,
    rawTag: s.tag,
  }));

  return (
    <Card>
      <CardHeader
        title="Lesson Tag Analytics"
        subtitle={`${data.length} tag${data.length !== 1 ? "s" : ""} tracked`}
      />
      <CardBody>
        {/* Pattern alerts */}
        {patternAlerts.length > 0 && (
          <div className="mb-4 space-y-2">
            {patternAlerts.map((a) => (
              <div
                key={a.tag}
                className="flex items-start gap-2 px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm"
              >
                <span className="shrink-0 mt-0.5">&#x26A0;</span>
                <span>
                  Your losses frequently share the tag &lsquo;{formatTag(a.tag)}&rsquo; &mdash; consider reviewing this pattern
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Horizontal bar chart */}
        <div className="mb-6">
          <ResponsiveContainer width="100%" height={Math.max(180, data.length * 40)}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
              <XAxis
                type="number"
                domain={[0, 100]}
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickFormatter={(v: number) => `${v}%`}
              />
              <YAxis
                type="category"
                dataKey="tag"
                tick={{ fill: "#9ca3af", fontSize: 12 }}
                width={120}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#111827",
                  border: "1px solid #374151",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number) => [`${value.toFixed(1)}%`, "Win Rate"]}
              />
              <Bar dataKey="win_rate" radius={[0, 4, 4, 0]} name="Win Rate" barSize={20}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={`bar-${index}`}
                    fill={entry.win_rate >= 50 ? "#10b981" : "#ef4444"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Stats table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left text-gray-500 text-xs uppercase tracking-wider py-2 px-2">Tag</th>
                <th className="text-right text-gray-500 text-xs uppercase tracking-wider py-2 px-2">Count</th>
                <th className="text-right text-gray-500 text-xs uppercase tracking-wider py-2 px-2">Wins</th>
                <th className="text-right text-gray-500 text-xs uppercase tracking-wider py-2 px-2">Losses</th>
                <th className="text-right text-gray-500 text-xs uppercase tracking-wider py-2 px-2">Win Rate</th>
                <th className="text-right text-gray-500 text-xs uppercase tracking-wider py-2 px-2">Avg Return</th>
              </tr>
            </thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.tag} className="border-b border-gray-800/50 hover:bg-gray-800/20">
                  <td className="py-2 px-2 text-gray-300">{formatTag(s.tag)}</td>
                  <td className="py-2 px-2 text-right text-gray-400 font-mono">{s.count}</td>
                  <td className="py-2 px-2 text-right text-emerald-400 font-mono">{s.win_count}</td>
                  <td className="py-2 px-2 text-right text-red-400 font-mono">{s.loss_count}</td>
                  <td className={`py-2 px-2 text-right font-mono font-medium ${s.win_rate >= 50 ? "text-emerald-400" : "text-red-400"}`}>
                    {s.win_rate.toFixed(1)}%
                  </td>
                  <td className={`py-2 px-2 text-right font-mono ${s.avg_return_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {s.avg_return_pct >= 0 ? "+" : ""}{s.avg_return_pct.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardBody>
    </Card>
  );
}
