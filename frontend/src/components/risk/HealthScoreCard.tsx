import { useApi } from "../../hooks/useApi";
import { getPortfolioHealthScore } from "../../api/endpoints";
import type { PortfolioHealthScore } from "../../api/types";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { SkeletonCard } from "../ui/Skeleton";
import ErrorAlert from "../shared/ErrorAlert";

// ---------------------------------------------------------------------------
// Sub-score progress bar
// ---------------------------------------------------------------------------

function ScoreBar({ label, score, detail }: { label: string; score: number; detail?: string }) {
  const barColor =
    score > 70
      ? "bg-emerald-500"
      : score >= 40
        ? "bg-amber-500"
        : "bg-red-500";

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-300 font-semibold">{Math.round(score)}</span>
      </div>
      <div className="w-full h-2 rounded-full bg-gray-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      {detail && <p className="text-xs text-gray-500">{detail}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overall score circle
// ---------------------------------------------------------------------------

function OverallScore({ score }: { score: number }) {
  const color =
    score > 70
      ? "text-emerald-400 border-emerald-500/40"
      : score >= 40
        ? "text-amber-400 border-amber-500/40"
        : "text-red-400 border-red-500/40";

  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={`w-20 h-20 rounded-full border-4 flex items-center justify-center ${color}`}
      >
        <span className="text-2xl font-bold">{Math.round(score)}</span>
      </div>
      <span className="text-xs text-gray-500">Overall</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function HealthScoreCard() {
  const {
    data,
    loading,
    error,
    refetch,
  } = useApi<PortfolioHealthScore>(() => getPortfolioHealthScore(), {
    cacheKey: "risk:health-score",
    ttlMs: 60_000,
  });

  if (loading) return <SkeletonCard className="h-[260px]" />;
  if (error) return <ErrorAlert message={error} onRetry={refetch} />;
  if (!data) {
    return (
      <Card>
        <CardHeader title="Portfolio Health" />
        <CardBody>
          <p className="text-sm text-gray-500">No health data available.</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Portfolio Health" subtitle="Composite health score across key dimensions" />
      <CardBody>
        <div className="flex gap-6 items-start">
          {/* Overall score circle */}
          <OverallScore score={data.overall_score} />

          {/* Sub-scores */}
          <div className="flex-1 space-y-3">
            <ScoreBar
              label="Diversification"
              score={data.diversification_score}
              detail={data.details.diversification}
            />
            <ScoreBar
              label="Risk"
              score={data.risk_score}
              detail={data.details.risk}
            />
            <ScoreBar
              label="Thesis Adherence"
              score={data.thesis_adherence_score}
              detail={data.details.thesis_adherence}
            />
            <ScoreBar
              label="Momentum"
              score={data.momentum_score}
              detail={data.details.momentum}
            />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
