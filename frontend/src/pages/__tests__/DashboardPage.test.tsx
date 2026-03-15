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
  BarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "bar-chart" }, children),
  Bar: () => null,
  Cell: () => null,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

// Mock ALL endpoint functions imported by DashboardPage and its children
vi.mock("../../api/endpoints", () => ({
  getPortfolio: vi.fn(),
  getAlerts: vi.fn(),
  getPositionHistory: vi.fn(),
  getValueHistory: vi.fn(),
  getWatchlist: vi.fn(),
  getRegime: vi.fn(),
  getRegimeHistory: vi.fn(),
  runMonitorCheck: vi.fn(),
  getLatestSummary: vi.fn(),
  generateSummary: vi.fn(),
  getSignalHistory: vi.fn(),
  getAccuracyStats: vi.fn(),
  getDailyReturn: vi.fn(),
  getPortfolioRisk: vi.fn(),
  getActivityFeed: vi.fn(),
  getWatchlistTargets: vi.fn(),
}));

import {
  getPortfolio,
  getAlerts,
  getPositionHistory,
  getValueHistory,
  getWatchlist,
  getRegime,
  getRegimeHistory,
  getLatestSummary,
  getSignalHistory,
  getAccuracyStats,
  getDailyReturn,
  getPortfolioRisk,
  getActivityFeed,
  getWatchlistTargets,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import DashboardPage from "../DashboardPage";

const mockGetPortfolio = vi.mocked(getPortfolio);
const mockGetAlerts = vi.mocked(getAlerts);
const mockGetPositionHistory = vi.mocked(getPositionHistory);
const mockGetValueHistory = vi.mocked(getValueHistory);
const mockGetWatchlist = vi.mocked(getWatchlist);
const mockGetRegime = vi.mocked(getRegime);
const mockGetRegimeHistory = vi.mocked(getRegimeHistory);
const mockGetLatestSummary = vi.mocked(getLatestSummary);
const mockGetSignalHistory = vi.mocked(getSignalHistory);
const mockGetAccuracyStats = vi.mocked(getAccuracyStats);
const mockGetDailyReturn = vi.mocked(getDailyReturn);
const mockGetPortfolioRisk = vi.mocked(getPortfolioRisk);
const mockGetActivityFeed = vi.mocked(getActivityFeed);
const mockGetWatchlistTargets = vi.mocked(getWatchlistTargets);

const mockPortfolio = {
  positions: [
    {
      ticker: "AAPL",
      asset_type: "stock",
      quantity: 10,
      avg_cost: 150,
      current_price: 170,
      entry_date: "2024-01-01",
      sector: "Tech",
      industry: null,
      cost_basis: 1500,
      market_value: 1700,
      unrealized_pnl: 200,
      unrealized_pnl_pct: 0.133,
      holding_days: 30,
      thesis_text: null,
      expected_return_pct: null,
      expected_hold_days: null,
      target_price: null,
      stop_loss: null,
      status: "open",
      exit_price: null,
      exit_date: null,
      exit_reason: null,
      realized_pnl: null,
    },
  ],
  cash: 50000,
  total_value: 51700,
  stock_exposure_pct: 0.033,
  crypto_exposure_pct: 0,
  cash_pct: 0.967,
  sector_breakdown: { Tech: 0.033 },
  top_concentration: [["AAPL", 0.033]],
};

/** Set up all secondary API mocks with reasonable defaults */
function mockSecondaryApis() {
  mockGetAlerts.mockResolvedValue({ data: [], warnings: [] });
  mockGetPositionHistory.mockResolvedValue({ data: [], warnings: [] });
  mockGetValueHistory.mockResolvedValue({ data: [], warnings: [] });
  mockGetWatchlist.mockResolvedValue({ data: [], warnings: [] });
  mockGetRegime.mockResolvedValue({
    data: { regime: "normal", confidence: 0.8, details: {} } as never,
    warnings: [],
  });
  mockGetRegimeHistory.mockResolvedValue({
    data: [
      { date: "2024-01-01", regime: "bull_market", confidence: 75, duration_days: 10 },
      { date: "2024-01-11", regime: "sideways", confidence: 60, duration_days: 5 },
    ],
    warnings: [],
  });
  // WeeklySummaryCard calls getLatestSummary directly (not via useApi)
  mockGetLatestSummary.mockRejectedValue({ status: 404, message: "Not found" });
  // SignalSummaryCard
  mockGetSignalHistory.mockResolvedValue({
    data: [
      { id: 1, ticker: "AAPL", final_signal: "BUY", final_confidence: 0.8, raw_score: 0.7, consensus_score: 0.75, regime: "normal", agent_signals: [], reasoning: "", created_at: "2024-01-01" },
      { id: 2, ticker: "GOOG", final_signal: "HOLD", final_confidence: 0.5, raw_score: 0.4, consensus_score: 0.45, regime: "normal", agent_signals: [], reasoning: "", created_at: "2024-01-02" },
      { id: 3, ticker: "TSLA", final_signal: "SELL", final_confidence: 0.6, raw_score: -0.5, consensus_score: -0.4, regime: "normal", agent_signals: [], reasoning: "", created_at: "2024-01-03" },
    ],
    warnings: [],
  });
  mockGetAccuracyStats.mockResolvedValue({
    data: {
      total_signals: 10,
      resolved_count: 8,
      win_count: 5,
      loss_count: 3,
      win_rate: 0.625,
      avg_confidence: 0.7,
      by_signal: {},
      by_asset_type: {},
      by_regime: {},
    },
    warnings: [],
  });
  mockGetDailyReturn.mockResolvedValue({
    data: { return_pct: 0.5, return_dollars: 250, date: "2025-03-15", previous_value: 51450, current_value: 51700 },
    warnings: [],
  });
  mockGetPortfolioRisk.mockResolvedValue({
    data: { daily_volatility: 0.01, annualized_volatility: 0.16, sharpe_ratio: 1.5, sortino_ratio: 2.0, max_drawdown_pct: -0.1, current_drawdown_pct: -0.02, var_95: -0.02, cvar_95: -0.03, best_day_pct: 0.03, worst_day_pct: -0.02, positive_days: 50, negative_days: 40, data_points: 90 } as never,
    warnings: [],
  });
  mockGetActivityFeed.mockResolvedValue({
    data: [
      { type: "daemon_run", timestamp: "2025-03-15T10:00:00Z", title: "daily_scan \u2014 success", detail: "Completed in 1200ms", severity: "info", icon: "cog" },
      { type: "alert", timestamp: "2025-03-15T09:30:00Z", title: "price_drop \u2014 AAPL", detail: "Price dropped 5%", severity: "high", icon: "bell" },
      { type: "signal", timestamp: "2025-03-15T09:00:00Z", title: "GOOG \u2192 BUY", detail: "Confidence: 78%", severity: "info", icon: "chart" },
    ] as never,
    warnings: [],
  });
  mockGetWatchlistTargets.mockResolvedValue({
    data: [
      { ticker: "MSFT", target_buy_price: 400, current_price: 390, distance_pct: -2.5, last_signal: "BUY", last_confidence: 0.75 },
      { ticker: "NVDA", target_buy_price: 800, current_price: 830, distance_pct: 3.75, last_signal: "HOLD", last_confidence: 0.6 },
    ],
    warnings: [],
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <DashboardPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
  });

  it("renders skeleton components while loading", () => {
    mockGetPortfolio.mockReturnValue(new Promise(() => {}));
    mockSecondaryApis();
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error alert when portfolio API rejects", async () => {
    mockGetPortfolio.mockRejectedValue(new Error("Server unavailable"));
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders Dashboard heading when data loads", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
    });
  });

  it("renders metric cards with portfolio value", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Portfolio Value")).toBeInTheDocument();
    });
    expect(screen.getByText("$51,700")).toBeInTheDocument();
    expect(screen.getByText("Cash")).toBeInTheDocument();
    expect(screen.getByText("$50,000")).toBeInTheDocument();
  });

  it("renders Top Movers card", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Top Movers")).toBeInTheDocument();
    });
  });

  it("renders Signal Summary card", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Signal Summary")).toBeInTheDocument();
    });
  });

  it("renders Market Regime History card", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Market Regime History")).toBeInTheDocument();
    });
  });

  it("renders regime history empty state when no data", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    mockGetRegimeHistory.mockResolvedValue({ data: [], warnings: [] });
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText("No regime history recorded yet."),
      ).toBeInTheDocument();
    });
  });

  it("renders Watchlist Near Target banner when targets exist", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Watchlist Near Target")).toBeInTheDocument();
    });
    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("NVDA")).toBeInTheDocument();
  });

  it("renders Recent Activity card with feed entries", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Recent Activity")).toBeInTheDocument();
    });
    expect(screen.getByText("daily_scan \u2014 success")).toBeInTheDocument();
    expect(screen.getByText("Price dropped 5%")).toBeInTheDocument();
  });
});
