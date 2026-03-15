import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeTicker, analyzeTickerCustom, getPortfolio } from "../api/endpoints";
import type { AnalysisResult as AnalysisResultType } from "../api/types";
import AnalyzeForm from "../components/analysis/AnalyzeForm";
import AnalysisResultComponent from "../components/analysis/AnalysisResult";
import WeightAdjuster from "../components/analysis/WeightAdjuster";
import ErrorAlert from "../components/shared/ErrorAlert";
import WarningsBanner from "../components/shared/WarningsBanner";
import { usePageTitle } from "../hooks/usePageTitle";
import { getCached, setCache, LONG_TTL_MS } from "../lib/cache";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SkeletonCard } from "../components/ui/Skeleton";
import { useToast } from "../contexts/ToastContext";

const LS_TICKER_KEY = "lastAnalyzedTicker";
const LS_ASSET_KEY = "lastAnalyzedAssetType";
const ANALYSIS_CACHE_KEY = "analysis:lastResult";

export default function AnalyzePage() {
  usePageTitle("Analyze");
  const navigate = useNavigate();
  const { toast } = useToast();

  // Restore last analysis from cache (instant show on return)
  const cachedAnalysis = getCached<AnalysisResultType>(ANALYSIS_CACHE_KEY, LONG_TTL_MS, true);

  const [result, setResult] = useState<AnalysisResultType | null>(cachedAnalysis?.data ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>(cachedAnalysis?.warnings ?? []);

  // Initial values resolved from localStorage > portfolio > SPY
  const [initialTicker, setInitialTicker] = useState("");
  const [initialAssetType, setInitialAssetType] = useState("stock");

  // Track last analyzed params for re-analysis with custom weights
  const [lastTicker, setLastTicker] = useState("");
  const [lastAssetType, setLastAssetType] = useState("stock");

  // Guard to auto-analyze only once
  const autoAnalyzed = useRef(false);

  const handleAnalyze = useCallback(
    async (ticker: string, assetType: string, adaptiveWeights: boolean) => {
      setLoading(true);
      setError(null);
      setResult(null);
      setWarnings([]);
      setLastTicker(ticker);
      setLastAssetType(assetType);
      try {
        const res = await analyzeTicker(ticker, assetType, adaptiveWeights);
        setResult(res.data);
        setWarnings(res.warnings);
        // Cache result so returning to this page is instant
        setCache(ANALYSIS_CACHE_KEY, res.data, res.warnings);
        // Persist ticker to localStorage
        localStorage.setItem(LS_TICKER_KEY, ticker);
        localStorage.setItem(LS_ASSET_KEY, assetType);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Analysis failed";
        setError(msg);
        toast.error("Analysis failed", msg);
      } finally {
        setLoading(false);
      }
    },
    [toast],
  );

  // Resolve initial ticker and auto-analyze
  useEffect(() => {
    if (autoAnalyzed.current) return;

    const storedTicker = localStorage.getItem(LS_TICKER_KEY);
    const storedAsset = localStorage.getItem(LS_ASSET_KEY);

    // If we already have a cached result, just set the form values — no refetch
    if (cachedAnalysis?.data && storedTicker) {
      setInitialTicker(storedTicker);
      setInitialAssetType(storedAsset ?? "stock");
      setLastTicker(storedTicker);
      setLastAssetType(storedAsset ?? "stock");
      autoAnalyzed.current = true;
      return;
    }

    if (storedTicker) {
      // Priority 1: localStorage
      setInitialTicker(storedTicker);
      setInitialAssetType(storedAsset ?? "stock");
      autoAnalyzed.current = true;
      handleAnalyze(storedTicker, storedAsset ?? "stock", false);
    } else {
      // Priority 2: portfolio first position, Priority 3: SPY
      getPortfolio()
        .then((res) => {
          if (autoAnalyzed.current) return;
          const positions = res.data?.positions;
          if (positions && positions.length > 0) {
            const first = positions[0]!;
            const assetType =
              first.asset_type === "btc" || first.asset_type === "eth"
                ? "crypto"
                : "stock";
            setInitialTicker(first.ticker);
            setInitialAssetType(assetType);
            autoAnalyzed.current = true;
            handleAnalyze(first.ticker, assetType, false);
          } else {
            // Fallback: SPY
            setInitialTicker("SPY");
            setInitialAssetType("stock");
            autoAnalyzed.current = true;
            handleAnalyze("SPY", "stock", false);
          }
        })
        .catch(() => {
          if (autoAnalyzed.current) return;
          // API unavailable, fallback to SPY
          setInitialTicker("SPY");
          setInitialAssetType("stock");
          autoAnalyzed.current = true;
          handleAnalyze("SPY", "stock", false);
        });
    }
  }, [handleAnalyze]);

  const handleCustomWeights = useCallback(
    async (weights: Record<string, number>) => {
      if (!lastTicker) return;
      setLoading(true);
      setError(null);
      setResult(null);
      setWarnings([]);
      try {
        const res = await analyzeTickerCustom(lastTicker, lastAssetType, weights);
        setResult(res.data);
        setWarnings(res.warnings);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Analysis failed";
        setError(msg);
        toast.error("Analysis failed", msg);
      } finally {
        setLoading(false);
      }
    },
    [lastTicker, lastAssetType, toast],
  );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Analysis</h1>

      <Card padding="md">
        <AnalyzeForm
          onAnalyze={handleAnalyze}
          loading={loading}
          initialTicker={initialTicker}
          initialAssetType={initialAssetType}
        />
      </Card>

      {loading && <SkeletonCard />}
      {error && <ErrorAlert message={error} />}
      <WarningsBanner warnings={warnings} />

      {result && (
        <>
          <Card padding="md">
            <AnalysisResultComponent data={result} />
          </Card>

          {/* Add to Portfolio action */}
          <Card padding="md">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-300">
                  Like the analysis?
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  Add {result.ticker} to your portfolio to start tracking it.
                </p>
              </div>
              <Button
                onClick={() => {
                  const currentPrice =
                    typeof result.ticker_info?.currentPrice === "number"
                      ? result.ticker_info.currentPrice
                      : typeof result.ticker_info?.current_price === "number"
                        ? result.ticker_info.current_price
                        : 0;
                  const params = new URLSearchParams({
                    add: "1",
                    ticker: result.ticker,
                    asset_type: result.asset_type,
                    avg_cost: String(currentPrice),
                  });
                  navigate(`/portfolio?${params.toString()}`);
                }}
                className="shrink-0"
              >
                Add to Portfolio
              </Button>
            </div>
          </Card>

          {/* Weight adjuster */}
          <WeightAdjuster
            assetType={lastAssetType}
            onApply={handleCustomWeights}
            loading={loading}
          />
        </>
      )}
    </div>
  );
}
