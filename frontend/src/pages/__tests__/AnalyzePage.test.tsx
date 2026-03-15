import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock recharts to avoid canvas/SVG issues in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
  AreaChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "area-chart" }, children),
  Area: () => null,
  BarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "bar-chart" }, children),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

// Mock ALL endpoint functions imported by AnalyzePage and its children
vi.mock("../../api/endpoints", () => ({
  analyzeTicker: vi.fn(),
  analyzeTickerCustom: vi.fn(),
  getPortfolio: vi.fn(),
  getCatalysts: vi.fn(),
  getPositionSize: vi.fn(),
  getPriceHistory: vi.fn(),
}));

import {
  analyzeTicker,
  getPortfolio,
  getCatalysts,
  getPositionSize,
  getPriceHistory,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import AnalyzePage from "../AnalyzePage";

const mockAnalyzeTicker = vi.mocked(analyzeTicker);
const mockGetPortfolio = vi.mocked(getPortfolio);
const mockGetCatalysts = vi.mocked(getCatalysts);
const mockGetPositionSize = vi.mocked(getPositionSize);
const mockGetPriceHistory = vi.mocked(getPriceHistory);

const mockResult = {
  ticker: "SPY",
  asset_type: "stock",
  final_signal: "BUY",
  final_confidence: 72,
  regime: "normal",
  agent_signals: [],
  reasoning: "Test reasoning",
  metrics: {
    raw_score: 0.5,
    consensus_score: 0.6,
    buy_count: 2,
    sell_count: 0,
    hold_count: 1,
    regime: "normal",
    weights_used: {},
    agent_contributions: {},
    buy_threshold: 0.3,
    sell_threshold: -0.3,
  },
  warnings: [],
  ticker_info: {},
};

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <AnalyzePage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("AnalyzePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
    vi.spyOn(Storage.prototype, "getItem").mockReturnValue(null);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {});
    // Default mocks for child components (PriceHistoryChart, CatalystPanel, PortfolioImpactPanel)
    mockGetPriceHistory.mockResolvedValue({ data: [], warnings: [] });
    mockGetCatalysts.mockRejectedValue(new Error("Not available"));
    mockGetPositionSize.mockRejectedValue(new Error("Not available"));
    // Default: getPortfolio returns empty positions so auto-analyze falls back to SPY
    mockGetPortfolio.mockResolvedValue({
      data: {
        positions: [],
        cash: 50000,
        total_value: 50000,
        stock_exposure_pct: 0,
        crypto_exposure_pct: 0,
        cash_pct: 1,
        sector_breakdown: {},
        top_concentration: [],
      } as never,
      warnings: [],
    });
  });

  it("renders Analysis heading", async () => {
    mockAnalyzeTicker.mockResolvedValue({
      data: mockResult as never,
      warnings: [],
    });
    renderPage();
    expect(screen.getByText("Analysis")).toBeInTheDocument();
  });

  it("renders skeleton while analyzeTicker is pending", async () => {
    mockAnalyzeTicker.mockReturnValue(new Promise(() => {}));
    renderPage();
    await waitFor(() => {
      const skeletons = document.querySelectorAll(".animate-pulse");
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  it("renders error alert when analyzeTicker rejects", async () => {
    mockAnalyzeTicker.mockRejectedValue(new Error("Analysis failed"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Analysis failed")).toBeInTheDocument();
    });
  });

  it("renders analysis result when data loads", async () => {
    mockAnalyzeTicker.mockResolvedValue({
      data: mockResult as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("SPY")).toBeInTheDocument();
    });
    expect(screen.getAllByText("BUY").length).toBeGreaterThan(0);
  });

  it("renders ticker input form", async () => {
    mockAnalyzeTicker.mockResolvedValue({
      data: mockResult as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Analysis")).toBeInTheDocument();
    });
    // AnalyzeForm renders a text input for ticker and an Analyze button
    expect(screen.getByRole("button", { name: /analyze/i })).toBeInTheDocument();
  });

  it("auto-analyzes SPY when localStorage is empty and portfolio has no positions", async () => {
    mockAnalyzeTicker.mockResolvedValue({
      data: mockResult as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(mockAnalyzeTicker).toHaveBeenCalledWith("SPY", "stock", false);
    });
  });
});
