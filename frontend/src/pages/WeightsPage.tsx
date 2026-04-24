import { Navigate } from "react-router-dom";

/**
 * Phase 06-02 (LIVE-03): the v1.0 donut-based WeightsPage is superseded by the
 * unified CalibrationPage which embeds the Agent Weights editor alongside the
 * per-agent calibration table. This component redirects for backward compatibility
 * with bookmarked /weights URLs and the sidebar nav shortcut.
 *
 * The old shape (buy_threshold, sell_threshold, crypto_factor_weights) was removed
 * in 06-01 when the agent_weights table replaced the legacy endpoint contract.
 */
export default function WeightsPage() {
  return <Navigate to="/calibration" replace />;
}
