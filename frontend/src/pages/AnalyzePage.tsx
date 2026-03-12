import { useState } from "react";
import { analyzeTicker } from "../api/endpoints";
import type { AnalysisResult as AnalysisResultType } from "../api/types";
import AnalyzeForm from "../components/analysis/AnalyzeForm";
import AnalysisResultComponent from "../components/analysis/AnalysisResult";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorAlert from "../components/shared/ErrorAlert";
import WarningsBanner from "../components/shared/WarningsBanner";

export default function AnalyzePage() {
  const [result, setResult] = useState<AnalysisResultType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  async function handleAnalyze(
    ticker: string,
    assetType: string,
    adaptiveWeights: boolean,
  ) {
    setLoading(true);
    setError(null);
    setResult(null);
    setWarnings([]);
    try {
      const res = await analyzeTicker(ticker, assetType, adaptiveWeights);
      setResult(res.data);
      setWarnings(res.warnings);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Analysis</h1>
      <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-800/50 rounded-xl p-5">
        <AnalyzeForm onAnalyze={handleAnalyze} loading={loading} />
      </div>
      {loading && <LoadingSpinner />}
      {error && <ErrorAlert message={error} />}
      <WarningsBanner warnings={warnings} />
      {result && (
        <div className="bg-gray-900/50 backdrop-blur-sm border border-gray-800/50 rounded-xl p-5">
          <AnalysisResultComponent data={result} />
        </div>
      )}
    </div>
  );
}
