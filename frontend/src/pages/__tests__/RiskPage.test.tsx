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
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
}));

// Mock ALL endpoint functions imported by RiskPage
vi.mock("../../api/endpoints", () => ({
  getPortfolioRisk: vi.fn(),
  getPortfolioCorrelations: vi.fn(),
  getValueHistory: vi.fn(),
}));

import {
  getPortfolioRisk,
  getPortfolioCorrelations,
  getValueHistory,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import RiskPage from "../RiskPage";

const mockGetPortfolioRisk = vi.mocked(getPortfolioRisk);
const mockGetPortfolioCorrelations = vi.mocked(getPortfolioCorrelations);
const mockGetValueHistory = vi.mocked(getValueHistory);

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
  correlation_matrix: {},
  avg_correlation: 0.5,
  high_correlation_pairs: [],
  concentration_risk: "LOW",
  tickers: ["AAPL"],
};

const mockValueHistory = [
  { date: "2024-01-01", total_value: 50000, cash: 48000, invested: 2000 },
  { date: "2024-01-02", total_value: 50100, cash: 48000, invested: 2100 },
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
});
