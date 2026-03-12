import { useState } from "react";
import { runBacktest, runBatchBacktest } from "../api/endpoints";
import type { BacktestResult, BatchResponse, BatchRow } from "../api/types";
import BacktestForm from "../components/backtest/BacktestForm";
import BacktestResults from "../components/backtest/BacktestResults";
import BatchForm from "../components/backtest/BatchForm";
import BatchResultsComponent from "../components/backtest/BatchResults";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorAlert from "../components/shared/ErrorAlert";

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
  const [mode, setMode] = useState<Mode>("single");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [singleResult, setSingleResult] = useState<BacktestResult | null>(null);
  const [batchRows, setBatchRows] = useState<BatchRow[] | null>(null);

  async function handleSingle(params: Parameters<typeof runBacktest>[0]) {
    setLoading(true);
    setError(null);
    setSingleResult(null);
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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Backtest</h1>

      <div className="flex gap-1 border-b border-gray-800/50">
        {(["single", "batch"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors capitalize ${
              mode === m
                ? "border-blue-500 text-white"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-800/50 rounded-xl p-5">
        {mode === "single" ? (
          <BacktestForm onSubmit={handleSingle} loading={loading} />
        ) : (
          <BatchForm onSubmit={handleBatch} loading={loading} />
        )}
      </div>

      {loading && <LoadingSpinner />}
      {error && <ErrorAlert message={error} />}
      {mode === "single" && singleResult && (
        <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-800/50 rounded-xl p-5">
          <BacktestResults data={singleResult} />
        </div>
      )}
      {mode === "batch" && batchRows && batchRows.length > 0 && (
        <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-800/50 rounded-xl p-5">
          <BatchResultsComponent rows={batchRows} />
        </div>
      )}
    </div>
  );
}
