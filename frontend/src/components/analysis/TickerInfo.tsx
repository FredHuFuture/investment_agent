import { formatCurrency } from "../../lib/formatters";

interface TickerInfoData {
  current_price?: number;
  name?: string;
  market_cap?: number;
  pe_ratio?: number;
  forward_pe?: number;
  beta?: number;
  dividend_yield?: number;
  sector?: string;
  industry?: string;
  "52w_high"?: number;
  "52w_low"?: number;
  pegRatio?: number;
  earningsGrowth?: number;
  recommendationMean?: number;
}

function formatLargeNumber(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return formatCurrency(n);
}

function Stat({ label, value }: { label: string; value: string | null }) {
  if (!value || value === "-") return null;
  return (
    <div className="flex justify-between py-1.5 border-b border-gray-800/30 last:border-0">
      <span className="text-xs text-gray-500">{label}</span>
      <span className="text-xs font-mono text-gray-300">{value}</span>
    </div>
  );
}

export default function TickerInfo({ info }: { info: Record<string, unknown> }) {
  const d = info as TickerInfoData;
  if (!d || Object.keys(d).length === 0) return null;

  const w52High = d["52w_high"];
  const w52Low = d["52w_low"];
  const price = d.current_price;

  // 52-week range bar
  let rangePct: number | null = null;
  if (price != null && w52High != null && w52Low != null && w52High > w52Low) {
    rangePct = ((price - w52Low) / (w52High - w52Low)) * 100;
  }

  return (
    <div className="space-y-3">
      {/* Header: name + price */}
      {(d.name || price != null) && (
        <div className="flex items-baseline justify-between">
          {d.name && (
            <span className="text-sm text-gray-300 truncate mr-2">{d.name}</span>
          )}
          {price != null && (
            <span className="text-lg font-semibold font-mono text-white">
              {formatCurrency(price)}
            </span>
          )}
        </div>
      )}

      {/* Sector / Industry */}
      {(d.sector || d.industry) && (
        <div className="text-[11px] text-gray-500">
          {[d.sector, d.industry].filter(Boolean).join(" / ")}
        </div>
      )}

      {/* 52-week range */}
      {rangePct != null && w52Low != null && w52High != null && (
        <div>
          <div className="flex justify-between text-[10px] text-gray-600 mb-1">
            <span>52W Low: {formatCurrency(w52Low)}</span>
            <span>52W High: {formatCurrency(w52High)}</span>
          </div>
          <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500"
              style={{ width: `${Math.min(100, Math.max(0, rangePct))}%` }}
            />
          </div>
        </div>
      )}

      {/* Key stats grid */}
      <div>
        <Stat label="Market Cap" value={d.market_cap != null ? formatLargeNumber(d.market_cap) : null} />
        <Stat label="P/E (TTM)" value={d.pe_ratio != null ? d.pe_ratio.toFixed(1) : null} />
        <Stat label="Forward P/E" value={d.forward_pe != null ? d.forward_pe.toFixed(1) : null} />
        <Stat label="PEG Ratio" value={d.pegRatio != null ? d.pegRatio.toFixed(2) : null} />
        <Stat label="Beta" value={d.beta != null ? d.beta.toFixed(2) : null} />
        <Stat
          label="Dividend Yield"
          value={d.dividend_yield != null ? `${(d.dividend_yield * 100).toFixed(2)}%` : null}
        />
        <Stat
          label="Earnings Growth"
          value={d.earningsGrowth != null ? `${(d.earningsGrowth * 100).toFixed(1)}%` : null}
        />
        <Stat
          label="Analyst Rating"
          value={d.recommendationMean != null ? d.recommendationMean.toFixed(1) : null}
        />
      </div>
    </div>
  );
}
