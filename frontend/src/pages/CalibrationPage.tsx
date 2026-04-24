import { useState, useCallback, useEffect, useRef } from "react";
import { useApi } from "../hooks/useApi";
import {
  getCalibrationAnalytics,
  getWeightsV2,
  applyIcIrWeights,
  overrideAgentWeight,
  rebuildCalibrationCorpus,
} from "../api/endpoints";
import type { CalibrationResponse, WeightsOverviewResponse } from "../api/types";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SkeletonCard } from "../components/ui/Skeleton";
import ErrorAlert from "../components/shared/ErrorAlert";
import WarningsBanner from "../components/shared/WarningsBanner";
import CalibrationTable from "../components/calibration/CalibrationTable";
import WeightsEditor from "../components/calibration/WeightsEditor";
import AssetTypeTabs, { type AssetType } from "../components/calibration/AssetTypeTabs";
import { usePageTitle } from "../hooks/usePageTitle";
import { useToast } from "../contexts/ToastContext";

/**
 * CalibrationPage (LIVE-02 + LIVE-03)
 *
 * Weekly review surface that combines:
 *  - Per-agent calibration table (Brier, IC, IC-IR, 90-day sparkline)
 *  - Embedded weights editor (Current vs Suggested, per-agent exclude toggle)
 *
 * Route: /calibration
 * Legacy /weights route redirects here via WeightsPage.tsx Navigate.
 */
export default function CalibrationPage() {
  usePageTitle("Calibration");
  const { toast } = useToast();
  const [assetType, setAssetType] = useState<AssetType>("stock");
  const [applying, setApplying] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  const mountedRef = useRef(true);
  const rebuildTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (rebuildTimeoutRef.current !== null) {
        clearTimeout(rebuildTimeoutRef.current);
      }
    };
  }, []);

  const calApi = useApi<CalibrationResponse>(
    () => getCalibrationAnalytics(),
    { cacheKey: "cal:calibration", ttlMs: 60_000 },
  );
  const weightsApi = useApi<WeightsOverviewResponse>(
    () => getWeightsV2(),
    { cacheKey: "cal:weights", ttlMs: 60_000 },
  );

  const refetchAll = useCallback(() => {
    calApi.refetch();
    weightsApi.refetch();
  }, [calApi, weightsApi]);

  async function handleApplyIcIr() {
    setApplying(true);
    try {
      await applyIcIrWeights();
      toast.success("IC-IR weights applied");
      weightsApi.refetch();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to apply IC-IR weights";
      toast.error(msg);
    } finally {
      setApplying(false);
    }
  }

  async function handleOverride(agent: string, excluded: boolean) {
    try {
      await overrideAgentWeight({ agent, asset_type: assetType, excluded });
      toast.success(`${agent} ${excluded ? "excluded" : "enabled"} for ${assetType}`);
      weightsApi.refetch();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Override failed";
      toast.error(msg);
    }
  }

  async function handleRebuildCorpus() {
    setRebuilding(true);
    try {
      const resp = await rebuildCalibrationCorpus();
      toast.success(
        `Corpus rebuild started (job ${resp.data.job_id.slice(0, 8)}…, ${resp.data.ticker_count} tickers)`,
      );
      // Schedule a background refetch after delay; cancelled on unmount to avoid
      // state updates on a dead component (WR-02).
      rebuildTimeoutRef.current = window.setTimeout(() => {
        if (!mountedRef.current) return;
        calApi.refetch();
        setRebuilding(false);
      }, 3_000);
    } catch (err) {
      setRebuilding(false);
      const msg = err instanceof Error ? err.message : "Rebuild failed";
      toast.error(msg);
    }
  }

  const loading = calApi.loading || weightsApi.loading;
  const error = calApi.error ?? weightsApi.error;
  const warnings = [...calApi.warnings, ...weightsApi.warnings];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Calibration</h1>
          <p className="text-sm text-gray-500 mt-1">
            Per-agent signal quality and weight management — weekly review surface
          </p>
        </div>
        <Button onClick={refetchAll} disabled={loading} variant="secondary">
          Refresh
        </Button>
      </div>

      {warnings.length > 0 && <WarningsBanner warnings={warnings} />}
      {error && <ErrorAlert message={error} onRetry={refetchAll} />}

      {loading && (
        <div className="space-y-6">
          <SkeletonCard className="h-[320px]" />
          <SkeletonCard className="h-[280px]" />
        </div>
      )}

      {/* Calibration metrics table */}
      {!loading && calApi.data && (
        <CalibrationTable
          data={calApi.data}
          onRebuildCorpus={handleRebuildCorpus}
          rebuildInProgress={rebuilding}
        />
      )}

      {/* Weights editor section — always shown when weights data available */}
      {!loading && weightsApi.data && (
        <Card>
          <div className="p-4 pb-0">
            <AssetTypeTabs value={assetType} onChange={setAssetType} />
          </div>
          <WeightsEditor
            data={weightsApi.data}
            assetType={assetType}
            onApplyIcIr={handleApplyIcIr}
            onOverride={handleOverride}
            applying={applying}
          />
        </Card>
      )}
    </div>
  );
}
