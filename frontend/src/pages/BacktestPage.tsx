import { useState } from "react";
import { runBacktest, runBatchBacktest } from "../api/endpoints";
import type { BacktestResult, BatchResponse, BatchRow } from "../api/types";
import BacktestForm from "../components/backtest/BacktestForm";
import BacktestResults from "../components/backtest/BacktestResults";
import BatchForm from "../components/backtest/BatchForm";
import BatchResultsComponent from "../components/backtest/BatchResults";
import { Card } from "../components/ui/Card";
import { SkeletonCard, SkeletonTable } from "../components/ui/Skeleton";
import { Button } from "../components/ui/Button";
import ErrorAlert from "../components/shared/ErrorAlert";
import { usePageTitle } from "../hooks/usePageTitle";

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
          <Button
            key={m}
            variant={mode === m ? "primary" : "ghost"}
            size="sm"
            onClick={() => setMode(m)}
            className={`capitalize rounded-b-none border-b-2 ${
              mode === m
                ? "border-blue-500"
                : "border-transparent"
            }`}
          >
            {m}
          </Button>
        ))}
      </div>

      <Card padding="md">
        {mode === "single" ? (
          <BacktestForm onSubmit={handleSingle} loading={loading} />
        ) : (
          <BatchForm onSubmit={handleBatch} loading={loading} />
        )}
      </Card>

      {loading && (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonTable rows={5} columns={6} />
        </div>
      )}
      {error && <ErrorAlert message={error} />}
      {mode === "single" && singleResult && (
        <Card padding="md">
          <BacktestResults data={singleResult} />
        </Card>
      )}
      {mode === "batch" && batchRows && batchRows.length > 0 && (
        <Card padding="md">
          <BatchResultsComponent rows={batchRows} />
        </Card>
      )}
    </div>
  );
}
