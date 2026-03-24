import { useState, useCallback, useRef } from "react";
import { runBacktest, runBatchBacktest } from "../api/endpoints";
import type { BacktestResult, BatchResponse, BatchRow } from "../api/types";
import BacktestForm from "../components/backtest/BacktestForm";
import BacktestResults from "../components/backtest/BacktestResults";
import BatchForm from "../components/backtest/BatchForm";
import BatchResultsComponent from "../components/backtest/BatchResults";
import SaveRunButton from "../components/backtest/SaveRunButton";
import BacktestHistory from "../components/backtest/BacktestHistory";
import BacktestComparison from "../components/backtest/BacktestComparison";
import PresetManager from "../components/backtest/PresetManager";
import { Card } from "../components/ui/Card";
import { SkeletonCard, SkeletonTable } from "../components/ui/Skeleton";
import { Button } from "../components/ui/Button";
import ErrorAlert from "../components/shared/ErrorAlert";
import { usePageTitle } from "../hooks/usePageTitle";
import type { SavedBacktestRun } from "../lib/backtestStorage";
import type { BacktestPreset } from "../lib/backtestPresets";

function flattenBatch(raw: BatchResponse): BatchRow[] {
  const rows: BatchRow[] = [];
  for (const [ticker, agentMap] of Object.entries(raw)) {
    for (const [agents, metrics] of Object.entries(agentMap)) {
      rows.push({ ticker, agents, metrics });
    }
  }
  return rows;
}

type Mode = "single" | "batch";

export default function BacktestPage() {
  usePageTitle("Backtest");
  const [mode, setMode] = useState<Mode>("single");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [singleResult, setSingleResult] = useState<BacktestResult | null>(null);
  const [batchRows, setBatchRows] = useState<BatchRow[] | null>(null);

  // History & comparison state
  const [showHistory, setShowHistory] = useState(false);
  const [comparisonRuns, setComparisonRuns] = useState<SavedBacktestRun[]>([]);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  // Preset manager state
  const [presetKey, setPresetKey] = useState(0);
  const [currentPresetValues, setCurrentPresetValues] = useState<BacktestPreset | null>(null);
  const formParamsRef = useRef<BacktestPreset>({
    name: "",
    ticker: "AAPL",
    startDate: "2023-01-01",
    endDate: "2025-12-31",
    assetType: "stock",
    capital: "100000",
    frequency: "weekly",
    posSize: "10",
    stopLoss: "10",
    takeProfit: "20",
    buyThreshold: "0.30",
    sellThreshold: "-0.30",
  });

  const handlePresetLoad = useCallback((preset: BacktestPreset) => {
    setCurrentPresetValues(preset);
    setPresetKey((k) => k + 1);
    // Also keep ref in sync so "Save Current" reflects loaded preset immediately
    formParamsRef.current = preset;
  }, []);

  const getCurrentParams = useCallback((): BacktestPreset => {
    return formParamsRef.current;
  }, []);

  // Track the last single-run params so we can pass them to SaveRunButton
  const [lastSingleParams, setLastSingleParams] = useState<{
    ticker: string;
    start_date: string;
    end_date: string;
    agents?: string[];
  } | null>(null);

  async function handleSingle(params: Parameters<typeof runBacktest>[0]) {
    // Sync the ref with whatever the form just submitted
    formParamsRef.current = {
      name: "",
      ticker: params.ticker,
      startDate: params.start_date,
      endDate: params.end_date,
      assetType: params.asset_type ?? "stock",
      capital: String(params.initial_capital ?? 100000),
      frequency: params.rebalance_frequency ?? "weekly",
      posSize: String((params.position_size_pct ?? 0.1) * 100),
      stopLoss: params.stop_loss_pct != null ? String(params.stop_loss_pct * 100) : "",
      takeProfit: params.take_profit_pct != null ? String(params.take_profit_pct * 100) : "",
      buyThreshold: String(params.buy_threshold ?? 0.3),
      sellThreshold: String(params.sell_threshold ?? -0.3),
    };
    setLoading(true);
    setError(null);
    setSingleResult(null);
    setLastSingleParams({
      ticker: params.ticker,
      start_date: params.start_date,
      end_date: params.end_date,
      agents: params.agents,
    });
    try {
      const res = await runBacktest(params);
      setSingleResult(res.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backtest failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleBatch(params: Parameters<typeof runBatchBacktest>[0]) {
    setLoading(true);
    setError(null);
    setBatchRows(null);
    try {
      const res = await runBatchBacktest(params);
      setBatchRows(flattenBatch(res.data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Batch backtest failed");
    } finally {
      setLoading(false);
    }
  }

  const handleRunSaved = useCallback(() => {
    setHistoryRefreshKey((k) => k + 1);
  }, []);

  const handleCompare = useCallback((runs: SavedBacktestRun[]) => {
    setComparisonRuns(runs);
  }, []);

  const handleCloseComparison = useCallback(() => {
    setComparisonRuns([]);
  }, []);

  return (
    <div className="space-y-6">
      {/* Page header with History toggle */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Backtest</h1>
        <Button
          size="sm"
          variant={showHistory ? "primary" : "secondary"}
          onClick={() => setShowHistory((v) => !v)}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
            />
          </svg>
          History
        </Button>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-1 border-b border-gray-800/50">
        {(["single", "batch"] as Mode[]).map((m) => (
          <Button
            key={m}
            variant={mode === m ? "primary" : "ghost"}
            size="sm"
            onClick={() => setMode(m)}
            className={`capitalize rounded-b-none border-b-2 ${
              mode === m
                ? "border-accent"
                : "border-transparent"
            }`}
          >
            {m}
          </Button>
        ))}
      </div>

      {/* Preset manager (single mode only) */}
      {mode === "single" && (
        <Card padding="md">
          <PresetManager onLoad={handlePresetLoad} getCurrentParams={getCurrentParams} />
        </Card>
      )}

      {/* Form */}
      <Card padding="md">
        {mode === "single" ? (
          <BacktestForm
            onSubmit={handleSingle}
            loading={loading}
            presetValues={currentPresetValues}
            presetKey={presetKey}
          />
        ) : (
          <BatchForm onSubmit={handleBatch} loading={loading} />
        )}
      </Card>

      {/* History panel (toggle) */}
      {showHistory && (
        <BacktestHistory
          onCompare={handleCompare}
          refreshKey={historyRefreshKey}
        />
      )}

      {/* Comparison overlay */}
      {comparisonRuns.length >= 2 && (
        <BacktestComparison
          runs={comparisonRuns}
          onClose={handleCloseComparison}
        />
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonTable rows={5} columns={6} />
        </div>
      )}

      {/* Error */}
      {error && <ErrorAlert message={error} />}

      {/* Single backtest results + save button */}
      {mode === "single" && singleResult && (
        <>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-400">Results</h2>
            {lastSingleParams && (
              <SaveRunButton
                result={singleResult}
                ticker={lastSingleParams.ticker}
                params={lastSingleParams}
                onSaved={handleRunSaved}
              />
            )}
          </div>
          <Card padding="md">
            <BacktestResults data={singleResult} />
          </Card>
        </>
      )}

      {/* Batch results */}
      {mode === "batch" && batchRows && batchRows.length > 0 && (
        <Card padding="md">
          <BatchResultsComponent rows={batchRows} />
        </Card>
      )}
    </div>
  );
}
