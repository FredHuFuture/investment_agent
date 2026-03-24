import { useState, useEffect, useRef, useMemo } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  CrosshairMode,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type Time,
} from "lightweight-charts";
import { getPriceHistory } from "../../api/endpoints";
import { formatCurrency } from "../../lib/formatters";
import type { OhlcvPoint } from "../../api/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type LwcCandle = CandlestickData<Time>;
type LwcVolume = HistogramData<Time>;

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
interface Props {
  ticker: string;
  assetType: string;
}

const PERIODS = [
  { key: "1mo", label: "1M" },
  { key: "3mo", label: "3M" },
  { key: "6mo", label: "6M" },
  { key: "1y", label: "1Y" },
  { key: "2y", label: "2Y" },
  { key: "5y", label: "5Y" },
];

const UP_COLOR = "#22c55e";
const DOWN_COLOR = "#ef4444";

export default function PriceHistoryChart({ ticker, assetType }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const [data, setData] = useState<OhlcvPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [period, setPeriod] = useState("1y");

  // Fetch data
  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    const mappedType =
      assetType === "crypto"
        ? ticker.toUpperCase().startsWith("ETH")
          ? "eth"
          : "btc"
        : "stock";

    getPriceHistory(ticker, mappedType, period)
      .then((res) => setData(res.data))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [ticker, assetType, period]);

  // Derived stats for header
  const { isUp, changePct, changeAbs, lastPrice } = useMemo(() => {
    if (data.length < 2)
      return { isUp: true, changePct: 0, changeAbs: 0, lastPrice: 0 };

    const fp = data[0]!.close;
    const lp = data[data.length - 1]!.close;
    const up = lp >= fp;

    return {
      isUp: up,
      changePct: ((lp - fp) / fp) * 100,
      changeAbs: lp - fp,
      lastPrice: lp,
    };
  }, [data]);

  // Convert OHLCV to lightweight-charts format
  const { candles, volumes } = useMemo(() => {
    const candles: LwcCandle[] = [];
    const volumes: LwcVolume[] = [];

    for (const p of data) {
      const time = p.date as unknown as Time;
      candles.push({
        time,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      });
      volumes.push({
        time,
        value: p.volume,
        color: p.close >= p.open
          ? "rgba(34,197,94,0.35)"
          : "rgba(239,68,68,0.35)",
      });
    }
    return { candles, volumes };
  }, [data]);

  // Create/update chart when container is available and data changes
  useEffect(() => {
    const el = containerRef.current;
    if (!el || candles.length === 0) return;

    // If chart already exists, just update data
    if (chartRef.current && candleSeriesRef.current && volumeSeriesRef.current) {
      candleSeriesRef.current.setData(candles);
      volumeSeriesRef.current.setData(volumes);
      chartRef.current.timeScale().fitContent();
      return;
    }

    // Create chart
    const chart = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#736e66",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(55,65,81,0.3)" },
        horzLines: { color: "rgba(55,65,81,0.3)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: "rgba(107,114,128,0.4)",
          width: 1,
          style: 2,
          labelBackgroundColor: "#2a2720",
        },
        horzLine: {
          color: "rgba(107,114,128,0.4)",
          width: 1,
          style: 2,
          labelBackgroundColor: "#2a2720",
        },
      },
      rightPriceScale: {
        borderColor: "rgba(55,65,81,0.3)",
        scaleMargins: { top: 0.05, bottom: 0.25 },
      },
      timeScale: {
        borderColor: "rgba(55,65,81,0.3)",
        timeVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      handleScroll: true,
      handleScale: true,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR,
      downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR,
      borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR,
      wickDownColor: DOWN_COLOR,
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    candleSeries.setData(candles);
    volumeSeries.setData(volumes);
    chart.timeScale().fitContent();

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Resize observer
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          chart.applyOptions({ width, height });
        }
      }
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [candles, volumes]);

  const hasData = data.length > 0;

  return (
    <div>
      {/* Top bar: price + change + period selector */}
      <div className="flex items-center justify-between mb-3">
        {/* Price + change */}
        <div className="flex items-baseline gap-3">
          {hasData ? (
            <>
              <span className="text-xl font-semibold font-mono text-white">
                {formatCurrency(lastPrice)}
              </span>
              <span
                className={`text-sm font-mono font-medium ${isUp ? "text-green-400" : "text-red-400"}`}
              >
                {isUp ? "+" : ""}
                {changeAbs.toFixed(2)}
              </span>
              <span
                className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                  isUp
                    ? "bg-green-500/15 text-green-400"
                    : "bg-red-500/15 text-red-400"
                }`}
              >
                {isUp ? "+" : ""}
                {changePct.toFixed(2)}%
              </span>
            </>
          ) : (
            <span className="text-sm text-gray-600">—</span>
          )}
        </div>

        {/* Period pills */}
        <div className="flex items-center gap-0.5 bg-gray-800/40 rounded-lg p-0.5">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`px-2.5 py-1 text-[10px] font-semibold rounded-md transition-all duration-150 ${
                period === p.key
                  ? "bg-gray-700 text-white shadow-sm"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart container — always in DOM */}
      <div className="relative h-64 w-full">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <div className="flex items-center gap-2 text-xs text-gray-600">
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeDasharray="32" strokeLinecap="round" />
              </svg>
              Loading...
            </div>
          </div>
        )}
        <div ref={containerRef} className="h-full w-full" />
      </div>
    </div>
  );
}
