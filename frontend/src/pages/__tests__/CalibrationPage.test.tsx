import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import { ToastProvider } from "../../contexts/ToastContext";
import { invalidateCache } from "../../lib/cache";

// Mock recharts for all sparkline usage inside the page hierarchy
vi.mock("recharts", () => ({
  LineChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "line-chart" }, children),
  Line: ({ stroke }: { stroke?: string }) =>
    React.createElement("div", { "data-testid": "sparkline-line", "data-stroke": stroke }),
  YAxis: () => null,
  AreaChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "area-chart" }, children),
  Area: () => null,
  XAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
}));

// Mock ALL endpoint functions imported by CalibrationPage and its children
vi.mock("../../api/endpoints", () => ({
  getCalibrationAnalytics: vi.fn(),
  getWeightsV2: vi.fn(),
  applyIcIrWeights: vi.fn(),
  overrideAgentWeight: vi.fn(),
  rebuildCalibrationCorpus: vi.fn(),
  getCalibrationRebuildJob: vi.fn(),
}));

import {
  getCalibrationAnalytics,
  getWeightsV2,
  applyIcIrWeights,
  overrideAgentWeight,
  rebuildCalibrationCorpus,
} from "../../api/endpoints";
import CalibrationPage from "../CalibrationPage";

const mockGetCalibrationAnalytics = vi.mocked(getCalibrationAnalytics);
const mockGetWeightsV2 = vi.mocked(getWeightsV2);
const mockApplyIcIrWeights = vi.mocked(applyIcIrWeights);
const mockOverrideAgentWeight = vi.mocked(overrideAgentWeight);
const mockRebuildCalibrationCorpus = vi.mocked(rebuildCalibrationCorpus);

function makeAgent(overrides = {}) {
  return {
    brier_score: 0.25,
    ic_5d: 0.12,
    ic_horizon: "5d",
    ic_ir: 0.8,
    sample_size: 60,
    preliminary_calibration: true,
    signal_source: "backtest_generated",
    rolling_ic: [0.1, 0.15, 0.08],
    ...overrides,
  };
}

const MOCK_CAL = {
  agents: {
    TechnicalAgent: makeAgent(),
    FundamentalAgent: makeAgent({
      brier_score: null,
      ic_5d: null,
      ic_ir: null,
      sample_size: 0,
      rolling_ic: [],
      note: "FundamentalAgent returns HOLD in backtest_mode (FOUND-04 contract)",
    }),
    MacroAgent: makeAgent(),
    SentimentAgent: makeAgent(),
    CryptoAgent: makeAgent(),
    SummaryAgent: makeAgent(),
  },
  corpus_metadata: {
    date_range: ["2024-01-01", "2024-12-28"] as [string, string],
    total_observations: 240,
    tickers_covered: ["AAPL", "NVDA"],
    n_agents: 5,
    survivorship_bias_warning: false,
  },
  horizon: "5d",
  window_days: 60,
};

const MOCK_WEIGHTS = {
  current: {
    stock: { TechnicalAgent: 0.25, FundamentalAgent: 0.40, MacroAgent: 0.20, SentimentAgent: 0.15 },
    btc: { CryptoAgent: 1.0 },
    eth: { CryptoAgent: 1.0 },
  },
  suggested_ic_ir: {
    stock: { TechnicalAgent: 0.30, FundamentalAgent: 0.35, MacroAgent: 0.20, SentimentAgent: 0.15 },
    btc: null,
    eth: null,
  },
  overrides: { stock: {}, btc: {}, eth: {} },
  source: "default" as const,
  computed_at: "2026-04-23T00:00:00Z",
  sample_size: 240,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <CalibrationPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("CalibrationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
    mockGetCalibrationAnalytics.mockResolvedValue({ data: MOCK_CAL, warnings: [] });
    mockGetWeightsV2.mockResolvedValue({ data: MOCK_WEIGHTS, warnings: [] });
  });

  // Test T7: smoke render — both APIs loaded, both sections visible
  it("renders calibration table and weights editor after data loads", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("cal-calibration-table")).toBeInTheDocument();
    });
    expect(screen.getByTestId("cal-weights-editor")).toBeInTheDocument();
  });

  // Test T8: empty corpus — CTA visible, weights editor still rendered
  it("shows empty-corpus CTA when total_observations is 0 and still renders weights editor", async () => {
    const emptyCalData = {
      ...MOCK_CAL,
      corpus_metadata: { ...MOCK_CAL.corpus_metadata, total_observations: 0 },
    };
    mockGetCalibrationAnalytics.mockResolvedValue({ data: emptyCalData, warnings: [] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("cal-empty-corpus-cta")).toBeInTheDocument();
    });
    // Weights editor still available for manual overrides
    expect(screen.getByTestId("cal-weights-editor")).toBeInTheDocument();
  });

  // Test T9: rebuild click wires to backend
  it("calls rebuildCalibrationCorpus when rebuild button is clicked", async () => {
    const emptyCalData = {
      ...MOCK_CAL,
      corpus_metadata: { ...MOCK_CAL.corpus_metadata, total_observations: 0 },
    };
    mockGetCalibrationAnalytics.mockResolvedValue({ data: emptyCalData, warnings: [] });
    mockRebuildCalibrationCorpus.mockResolvedValue({
      data: { job_id: "abc123def456", status: "started", ticker_count: 3 },
      warnings: [],
    });

    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("cal-rebuild-corpus-button")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByTestId("cal-rebuild-corpus-button"));
    expect(mockRebuildCalibrationCorpus).toHaveBeenCalledOnce();
  });

  it("shows heading 'Calibration'", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Calibration")).toBeInTheDocument();
    });
  });

  it("renders asset type tabs for switching between stock/btc/eth", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("cal-asset-type-tab-stock")).toBeInTheDocument();
    });
    expect(screen.getByTestId("cal-asset-type-tab-btc")).toBeInTheDocument();
    expect(screen.getByTestId("cal-asset-type-tab-eth")).toBeInTheDocument();
  });

  it("shows apply IC-IR button in weights editor section", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("cal-apply-ic-ir-button")).toBeInTheDocument();
    });
  });

  it("calls applyIcIrWeights when apply button is clicked", async () => {
    mockApplyIcIrWeights.mockResolvedValue({
      data: { applied: true, weights: {}, source: "ic_ir", sample_size: 240 },
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("cal-apply-ic-ir-button")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByTestId("cal-apply-ic-ir-button"));
    expect(mockApplyIcIrWeights).toHaveBeenCalledOnce();
  });

  it("calls overrideAgentWeight when exclude toggle is clicked", async () => {
    mockOverrideAgentWeight.mockResolvedValue({
      data: {
        agent: "SentimentAgent",
        asset_type: "stock",
        excluded: true,
        manual_override: true,
        renormalized_weights: { TechnicalAgent: 0.294, FundamentalAgent: 0.471, MacroAgent: 0.235 },
        source: "manual",
      },
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("cal-exclude-toggle-stock-SentimentAgent")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByTestId("cal-exclude-toggle-stock-SentimentAgent"));
    expect(mockOverrideAgentWeight).toHaveBeenCalledWith({
      agent: "SentimentAgent",
      asset_type: "stock",
      excluded: true,
    });
  });

  // Test WR-02: unmount during pending rebuild timeout must not trigger state update
  it("does not call refetch or setRebuilding after unmount during pending rebuild (WR-02)", async () => {
    const emptyCalData = {
      ...MOCK_CAL,
      corpus_metadata: { ...MOCK_CAL.corpus_metadata, total_observations: 0 },
    };
    mockGetCalibrationAnalytics.mockResolvedValue({ data: emptyCalData, warnings: [] });
    mockRebuildCalibrationCorpus.mockResolvedValue({
      data: { job_id: "abc123def456", status: "started", ticker_count: 3 },
      warnings: [],
    });

    const { unmount } = renderPage();

    // Wait for the rebuild button to appear using real timers
    await waitFor(() => {
      expect(screen.getByTestId("cal-rebuild-corpus-button")).toBeInTheDocument();
    });

    // Click rebuild and let the async handler complete (still real timers here)
    await userEvent.click(screen.getByTestId("cal-rebuild-corpus-button"));
    expect(mockRebuildCalibrationCorpus).toHaveBeenCalledOnce();

    // Snapshot call count before unmount — the 3s window.setTimeout is now pending
    const callCountBeforeUnmount = mockGetCalibrationAnalytics.mock.calls.length;

    // Switch to fake timers then unmount — useEffect cleanup clears the pending timeout
    vi.useFakeTimers();
    try {
      unmount();

      // Advance well past the 3s delay; the timeout was cleared so callback never runs
      act(() => {
        vi.advanceTimersByTime(5_000);
      });

      // No additional fetch should have occurred after unmount
      expect(mockGetCalibrationAnalytics.mock.calls.length).toBe(callCountBeforeUnmount);
    } finally {
      vi.useRealTimers();
    }
  });
});
