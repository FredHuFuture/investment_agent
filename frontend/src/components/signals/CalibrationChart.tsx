import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { CalibrationBucket } from "../../api/types";

export default function CalibrationChart({
  data,
}: {
  data: CalibrationBucket[];
}) {
  if (data.length === 0) return null;
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <XAxis dataKey="bucket" tick={{ fill: "#918b82", fontSize: 12 }} />
          <YAxis
            tick={{ fill: "#918b82", fontSize: 12 }}
            domain={[0, 100]}
            label={{
              value: "Accuracy %",
              angle: -90,
              position: "insideLeft",
              fill: "#918b82",
              fontSize: 12,
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#161410",
              border: "1px solid #2a2720",
            }}
            formatter={(v: number) => `${v.toFixed(1)}%`}
          />
          <ReferenceLine y={50} stroke="#4b5563" strokeDasharray="3 3" />
          <Bar dataKey="accuracy_pct" fill="#32af78" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
