import type { WatchlistItem, AnalysisResult } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import SignalBadge from "../shared/SignalBadge";
import { formatRelativeDate } from "../../lib/formatters";

interface ComparisonTableProps {
  items: WatchlistItem[];
  analysisResults: Record<string, AnalysisResult>;
  onClose: () => void;
}

export default function ComparisonTable({
  items,
  analysisResults,
  onClose,
}: ComparisonTableProps) {
  if (items.length < 2) {
    return (
      <Card padding="md">
        <p className="text-sm text-gray-500">
          Select at least 2 tickers to compare.
        </p>
      </Card>
    );
  }

  const rows: {
    label: string;
    values: (ticker: WatchlistItem) => React.ReactNode;
  }[] = [
    {
      label: "Signal",
      values: (item) =>
        item.last_signal ? (
          <SignalBadge signal={item.last_signal} />
        ) : (
          <span className="text-gray-600">-</span>
        ),
    },
    {
      label: "Confidence",
      values: (item) =>
        item.last_confidence != null ? (
          <span className="text-gray-300">
            {item.last_confidence.toFixed(1)}%
          </span>
        ) : (
          <span className="text-gray-600">-</span>
        ),
    },
    {
      label: "Target Buy Price",
      values: (item) =>
        item.target_buy_price != null ? (
          <span className="text-gray-300">
            ${item.target_buy_price.toFixed(2)}
          </span>
        ) : (
          <span className="text-gray-600">-</span>
        ),
    },
    {
      label: "Last Analysis",
      values: (item) => (
        <span className="text-gray-400 text-xs">
          {item.last_analysis_at
            ? formatRelativeDate(item.last_analysis_at)
            : "Never"}
        </span>
      ),
    },
    {
      label: "Notes",
      values: (item) => (
        <span className="text-gray-400 text-xs truncate block max-w-[150px]">
          {item.notes || "-"}
        </span>
      ),
    },
    {
      label: "Regime",
      values: (item) => {
        const a = analysisResults[item.ticker];
        return a ? (
          <span className="text-gray-400 text-xs">{a.regime}</span>
        ) : (
          <span className="text-gray-600">-</span>
        );
      },
    },
  ];

  return (
    <Card className="overflow-hidden">
      <CardHeader
        title="Comparison"
        subtitle={`${items.length} tickers selected`}
        action={
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 text-sm"
          >
            Close
          </button>
        }
      />
      <CardBody className="overflow-x-auto !p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800/50 text-xs text-gray-500 uppercase tracking-wider">
              <th className="text-left px-4 py-3 sticky left-0 bg-gray-900/80">
                Metric
              </th>
              {items.map((item) => (
                <th
                  key={item.ticker}
                  className="text-center px-4 py-3 font-mono font-bold text-white"
                >
                  {item.ticker}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.label}
                className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors"
              >
                <td className="px-4 py-2.5 text-gray-400 text-xs font-medium sticky left-0 bg-gray-900/80">
                  {row.label}
                </td>
                {items.map((item) => (
                  <td key={item.ticker} className="px-4 py-2.5 text-center">
                    {row.values(item)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
