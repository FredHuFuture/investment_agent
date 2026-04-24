import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { WeightsOverviewResponse } from "../../../api/types";

// Mock the endpoint functions used by WeightsEditor
vi.mock("../../../api/endpoints", () => ({
  applyIcIrWeights: vi.fn(),
  overrideAgentWeight: vi.fn(),
  // other endpoints used elsewhere
  getCalibrationAnalytics: vi.fn(),
  getWeightsV2: vi.fn(),
  rebuildCalibrationCorpus: vi.fn(),
  getCalibrationRebuildJob: vi.fn(),
}));

import WeightsEditor from "../WeightsEditor";

const MOCK_WEIGHTS: WeightsOverviewResponse = {
  current: {
    stock: {
      TechnicalAgent: 0.25,
      FundamentalAgent: 0.40,
      MacroAgent: 0.20,
      SentimentAgent: 0.15,
    },
    btc: { CryptoAgent: 1.0 },
    eth: { CryptoAgent: 1.0 },
  },
  suggested_ic_ir: {
    stock: {
      TechnicalAgent: 0.30,
      FundamentalAgent: 0.35,
      MacroAgent: 0.20,
      SentimentAgent: 0.15,
    },
    btc: null,
    eth: null,
  },
  overrides: {
    stock: {},
    btc: {},
    eth: {},
  },
  source: "default",
  computed_at: "2026-04-23T00:00:00Z",
  sample_size: 240,
};

function renderEditor(
  overrides: Partial<WeightsOverviewResponse> = {},
  assetType: "stock" | "btc" | "eth" = "stock",
  handlers: { onApplyIcIr?: () => Promise<void>; onOverride?: (agent: string, excluded: boolean) => Promise<void> } = {},
) {
  const data = { ...MOCK_WEIGHTS, ...overrides };
  return render(
    <WeightsEditor
      data={data}
      assetType={assetType}
      onApplyIcIr={handlers.onApplyIcIr ?? vi.fn().mockResolvedValue(undefined)}
      onOverride={handlers.onOverride ?? vi.fn().mockResolvedValue(undefined)}
      applying={false}
    />,
  );
}

describe("WeightsEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Test T2: renders current + suggested + delta for stock agents
  it("renders Current, Suggested, Delta columns for stock agents", () => {
    renderEditor();
    // All 4 stock agents should appear
    expect(screen.getByText("TechnicalAgent")).toBeInTheDocument();
    expect(screen.getByText("FundamentalAgent")).toBeInTheDocument();
    expect(screen.getByText("MacroAgent")).toBeInTheDocument();
    expect(screen.getByText("SentimentAgent")).toBeInTheDocument();
    // Current weight for TechnicalAgent: 25.0%
    expect(screen.getByTestId("cal-current-stock-TechnicalAgent")).toHaveTextContent("25.0%");
  });

  // Test T3: apply button disabled when suggested_ic_ir is null
  it("disables apply button when suggested_ic_ir for asset type is null", () => {
    renderEditor({}, "btc");
    const applyBtn = screen.getByTestId("cal-apply-ic-ir-button");
    expect(applyBtn).toBeDisabled();
    expect(applyBtn).toHaveAttribute("title", expect.stringContaining("populate corpus"));
  });

  // Test T4: apply button calls onApplyIcIr
  it("calls onApplyIcIr when apply button is clicked (stock has suggested)", async () => {
    const onApply = vi.fn().mockResolvedValue(undefined);
    renderEditor({}, "stock", { onApplyIcIr: onApply });
    const applyBtn = screen.getByTestId("cal-apply-ic-ir-button");
    expect(applyBtn).not.toBeDisabled();
    await userEvent.click(applyBtn);
    expect(onApply).toHaveBeenCalledOnce();
  });

  // Test T5: override toggle calls onOverride with correct args
  it("calls onOverride with agent name and excluded=true when toggle is checked", async () => {
    const onOverride = vi.fn().mockResolvedValue(undefined);
    renderEditor({}, "stock", { onOverride });
    const toggle = screen.getByTestId("cal-exclude-toggle-stock-SentimentAgent");
    expect(toggle).not.toBeChecked();
    await userEvent.click(toggle);
    expect(onOverride).toHaveBeenCalledWith("SentimentAgent", true);
  });

  // Test T6: source badge shows correct color by source
  it("shows Default badge in gray when source is default", () => {
    renderEditor({ source: "default" });
    expect(screen.getByTestId("cal-weights-source-badge")).toHaveTextContent("Default");
  });

  it("shows IC-IR badge in green when source is ic_ir", () => {
    renderEditor({ source: "ic_ir" });
    const badge = screen.getByTestId("cal-weights-source-badge");
    expect(badge).toHaveTextContent("IC-IR");
    expect(badge.className).toMatch(/green/);
  });

  it("shows Manual badge in amber when source is manual", () => {
    renderEditor({ source: "manual" });
    const badge = screen.getByTestId("cal-weights-source-badge");
    expect(badge).toHaveTextContent("Manual");
    expect(badge.className).toMatch(/amber/);
  });

  // Test T11: renormalized_weights update after override is handled by parent (onOverride callback)
  it("unchecks the toggle after onOverride resolves when starting excluded", async () => {
    const overridesWithExcluded: WeightsOverviewResponse = {
      ...MOCK_WEIGHTS,
      overrides: {
        stock: { SentimentAgent: { excluded: true, manual_override: true } },
        btc: {},
        eth: {},
      },
    };
    const onOverride = vi.fn().mockResolvedValue(undefined);
    renderEditor(overridesWithExcluded, "stock", { onOverride });
    const toggle = screen.getByTestId("cal-exclude-toggle-stock-SentimentAgent");
    expect(toggle).toBeChecked();
    await userEvent.click(toggle);
    expect(onOverride).toHaveBeenCalledWith("SentimentAgent", false);
  });

  it("shows manual label for manually overridden agents", () => {
    const overridesWithManual: WeightsOverviewResponse = {
      ...MOCK_WEIGHTS,
      overrides: {
        stock: { TechnicalAgent: { excluded: false, manual_override: true } },
        btc: {},
        eth: {},
      },
    };
    renderEditor(overridesWithManual, "stock");
    expect(screen.getByText("manual")).toBeInTheDocument();
  });
});
