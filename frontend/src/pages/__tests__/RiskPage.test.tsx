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
  ComposedChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "composed-chart" }, children),
  Area: () => null,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
}));

// Mock ALL endpoint functions imported by RiskPage (and StressTestPanel + MonteCarloPanel)
vi.mock("../../api/endpoints", () => ({
  getPortfolioRisk: vi.fn(),
  getPortfolioCorrelations: vi.fn(),
  getValueHistory: vi.fn(),
  getStressScenarios: vi.fn(),
  getMonteCarloSimulation: vi.fn(),
}));

import {
  getPortfolioRisk,
  getPortfolioCorrelations,
  getValueHistory,
  getStressScenarios,
  getMonteCarloSimulation,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import RiskPage from "../RiskPage";

const mockGetPortfolioRisk = vi.mocked(getPortfolioRisk);
const mockGetPortfolioCorrelations = vi.mocked(getPortfolioCorrelations);
const mockGetValueHistory = vi.mocked(getValueHistory);
const mockGetStressScenarios = vi.mocked(getStressScenarios);
const mockGetMonteCarloSimulation = vi.mocked(getMonteCarloSimulation);

const mockRisk = {
  daily_volatility: 0.012,
  annualized_volatility: 0.19,
  sharpe_ratio: 1.5,
  sortino_ratio: 2.1,
  max_drawdown_pct: -0.15,
  current_drawdown_pct: -0.03,
  var_95: -0.025,
  cvar_95: -0.035,
  best_day_pct: 0.04,
  worst_day_pct: -0.03,
  positive_days: 55,
  negative_days: 35,
  data_points: 90,
};

const mockCorrelations = {
  correlation_matrix: { "AAPL:MSFT": 0.85, "AAPL:GOOG": 0.45, "MSFT:GOOG": 0.62 },
  avg_correlation: 0.64,
  high_correlation_pairs: [["AAPL", "MSFT", 0.85]] as Array<[string, string, number]>,
  concentration_risk: "MODERATE",
  tickers: ["AAPL", "MSFT", "GOOG"],
};

const mockValueHistory = [
  { date: "2024-01-01", total_value: 50000, cash: 48000, invested: 2000 },
  { date: "2024-01-02", total_value: 50100, cash: 48000, invested: 2100 },
];

const mockStressScenarios = [
  {
    name: "2008 Financial Crisis",
    description: "Broad equity collapse and crypto sell-off mirroring 2008 conditions",
    portfolio_impact_pct: -12.5,
    affected_positions: [
      { ticker: "AAPL", impact_pct: -38.0 },
      { ticker: "BTC", impact_pct: -50.0 },
    ],
  },
  {
    name: "COVID Crash",
    description: "Rapid market sell-off similar to March 2020",
    portfolio_impact_pct: -10.2,
    affected_positions: [
      { ticker: "AAPL", impact_pct: -34.0 },
    ],
  },
];

/** Set up all API mocks with valid data */
function mockAllApis() {
  mockGetPortfolioRisk.mockResolvedValue({
    data: mockRisk as never,
    warnings: [],
  });
  mockGetPortfolioCorrelations.mockResolvedValue({
    data: mockCorrelations as never,
    warnings: [],
  });
  mockGetValueHistory.mockResolvedValue({
    data: mockValueHistory as never,
    warnings: [],
  });
  mockGetStressScenarios.mockResolvedValue({
    data: mockStressScenarios as never,
    warnings: [],
  });
  mockGetMonteCarloSimulation.mockResolvedValue({
    data: {
      percentiles: { p5: [100], p25: [105], p50: [110], p75: [115], p95: [120] },
      horizon_days: 30,
      simulations: 1000,
      dates: ["2025-03-15"],
      current_value: 100000,
    } as never,
    warnings: [],
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <RiskPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("RiskPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
  });

  it("renders skeleton while loading", () => {
    mockGetPortfolioRisk.mockReturnValue(new Promise(() => {}));
    mockGetPortfolioCorrelations.mockReturnValue(new Promise(() => {}));
    mockGetValueHistory.mockReturnValue(new Promise(() => {}));
    mockGetStressScenarios.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error alert when API rejects", async () => {
    mockGetPortfolioRisk.mockRejectedValue(new Error("Server unavailable"));
    mockGetPortfolioCorrelations.mockResolvedValue({
      data: mockCorrelations as never,
      warnings: [],
    });
    mockGetValueHistory.mockResolvedValue({
      data: mockValueHistory as never,
      warnings: [],
    });
    mockGetStressScenarios.mockResolvedValue({
      data: mockStressScenarios as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders Risk Dashboard heading when data loads", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Risk Dashboard")).toBeInTheDocument();
    });
  });

  it("renders risk metric cards (Annualized Volatility)", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Annualized Volatility")).toBeInTheDocument();
    });
    expect(screen.getByText("19.0%")).toBeInTheDocument();
  });

  it("renders Sharpe Ratio metric card", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Sharpe Ratio")).toBeInTheDocument();
    });
    expect(screen.getByText("1.50")).toBeInTheDocument();
  });

  it("renders Max Drawdown metric card", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Max Drawdown")).toBeInTheDocument();
    });
    expect(screen.getByText("-15.0%")).toBeInTheDocument();
  });

  it("renders Stress Test Scenarios heading", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Stress Test Scenarios")).toBeInTheDocument();
    });
  });

  it("renders stress test scenario names", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2008 Financial Crisis")).toBeInTheDocument();
    });
    expect(screen.getByText("COVID Crash")).toBeInTheDocument();
  });

  it("renders stress test portfolio impact percentages", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("-12.50%")).toBeInTheDocument();
    });
    expect(screen.getByText("-10.20%")).toBeInTheDocument();
  });

  it("renders stress test skeleton while loading", () => {
    mockGetPortfolioRisk.mockReturnValue(new Promise(() => {}));
    mockGetPortfolioCorrelations.mockReturnValue(new Promise(() => {}));
    mockGetValueHistory.mockReturnValue(new Promise(() => {}));
    mockGetStressScenarios.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    // Main page skeletons + stress test skeleton
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders Correlation Matrix card with heatmap data", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      // Both the inline CorrelationMatrix and CorrelationHeatmap render "Correlation Matrix"
      const headings = screen.getAllByText("Correlation Matrix");
      expect(headings.length).toBeGreaterThanOrEqual(1);
    });
    // Verify correlation values from the heatmap are rendered
    const cells085 = screen.getAllByText("0.85");
    expect(cells085.length).toBeGreaterThanOrEqual(1);
    // Verify the concentration risk badge renders
    const badges = screen.getAllByText("MODERATE");
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });
});
