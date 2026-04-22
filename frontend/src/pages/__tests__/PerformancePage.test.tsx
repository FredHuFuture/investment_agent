import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock recharts to avoid canvas/SVG issues in jsdom
vi.mock("recharts", () => ({
  AreaChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "area-chart" }, children),
  Area: () => null,
  BarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "bar-chart" }, children),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
  Cell: () => null,
  ReferenceLine: () => null,
  ComposedChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "composed-chart" }, children),
  Line: () => null,
  LineChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "line-chart" }, children),
}));

// Mock ALL endpoint functions imported by PerformancePage
vi.mock("../../api/endpoints", () => ({
  getValueHistory: vi.fn(),
  getPerformanceSummary: vi.fn(),
  getMonthlyReturns: vi.fn(),
  getTopPerformers: vi.fn(),
  getBenchmarkComparison: vi.fn(),
  getCumulativePnl: vi.fn(),
  getDrawdownSeries: vi.fn(),
  getRollingSharpe: vi.fn(),
  getMonthlyHeatmap: vi.fn(),
  getPerformanceAttribution: vi.fn(),
  compareSnapshots: vi.fn(),
  getSectorPerformance: vi.fn(),
  // Phase 04-03 additions
  getReturns: vi.fn(),
  getDailyPnl: vi.fn(),
  BENCHMARK_OPTIONS: ["SPY", "QQQ", "TLT", "GLD", "BTC-USD"] as const,
}));

import {
  getValueHistory,
  getPerformanceSummary,
  getMonthlyReturns,
  getTopPerformers,
  getBenchmarkComparison,
  getCumulativePnl,
  getDrawdownSeries,
  getRollingSharpe,
  getMonthlyHeatmap,
  getPerformanceAttribution,
  compareSnapshots,
  getSectorPerformance,
  getReturns,
  getDailyPnl,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import PerformancePage from "../PerformancePage";

const mockGetValueHistory = vi.mocked(getValueHistory);
const mockGetPerformanceSummary = vi.mocked(getPerformanceSummary);
const mockGetMonthlyReturns = vi.mocked(getMonthlyReturns);
const mockGetTopPerformers = vi.mocked(getTopPerformers);
const mockGetBenchmarkComparison = vi.mocked(getBenchmarkComparison);
const mockGetCumulativePnl = vi.mocked(getCumulativePnl);
const mockGetDrawdownSeries = vi.mocked(getDrawdownSeries);
const mockGetRollingSharpe = vi.mocked(getRollingSharpe);
const mockGetMonthlyHeatmap = vi.mocked(getMonthlyHeatmap);
const mockGetPerformanceAttribution = vi.mocked(getPerformanceAttribution);
const mockCompareSnapshots = vi.mocked(compareSnapshots);
const mockGetSectorPerformance = vi.mocked(getSectorPerformance);
const mockGetReturns = vi.mocked(getReturns);
const mockGetDailyPnl = vi.mocked(getDailyPnl);

const mockPerformanceSummary = {
  total_realized_pnl: 5000,
  win_count: 8,
  loss_count: 3,
  win_rate: 0.727,
  avg_win_pct: 0.15,
  avg_loss_pct: -0.08,
  best_trade: { ticker: "NVDA", return_pct: 0.45, pnl: 2000 },
  worst_trade: { ticker: "TSLA", return_pct: -0.12, pnl: -500 },
  avg_hold_days: 45,
  total_trades: 11,
  profit_factor: 2.5,
  expectancy: 3.2,
  max_consecutive_wins: 5,
  max_consecutive_losses: 2,
};

/** Set up all API mocks with reasonable defaults */
function mockAllApis() {
  mockGetValueHistory.mockResolvedValue({ data: [] as never, warnings: [] });
  mockGetPerformanceSummary.mockResolvedValue({
    data: mockPerformanceSummary as never,
    warnings: [],
  });
  mockGetMonthlyReturns.mockResolvedValue({ data: [] as never, warnings: [] });
  mockGetTopPerformers.mockResolvedValue({
    data: { best: [], worst: [] } as never,
    warnings: [],
  });
  mockGetBenchmarkComparison.mockResolvedValue({
    data: {
      benchmark_ticker: "SPY",
      portfolio_return_pct: 12.5,
      benchmark_return_pct: 8.2,
      alpha_pct: 4.3,
      data_points: 1,
      series: [{ date: "2026-01-01", portfolio_indexed: 100, benchmark_indexed: 100 }],
    } as never,
    warnings: [],
  });
  mockGetCumulativePnl.mockResolvedValue({ data: [] as never, warnings: [] });
  mockGetDrawdownSeries.mockResolvedValue({ data: [] as never, warnings: [] });
  mockGetRollingSharpe.mockResolvedValue({ data: [] as never, warnings: [] });
  mockGetMonthlyHeatmap.mockResolvedValue({ data: [] as never, warnings: [] });
  mockGetPerformanceAttribution.mockResolvedValue({
    data: [
      { ticker: "AAPL", sector: "Technology", pnl: 1200, pnl_pct: 15.5, contribution_pct: 48.0, status: "active" },
      { ticker: "MSFT", sector: "Technology", pnl: 800, pnl_pct: 10.2, contribution_pct: 32.0, status: "active" },
      { ticker: "TSLA", sector: "Automotive", pnl: -500, pnl_pct: -8.3, contribution_pct: -20.0, status: "closed" },
    ] as never,
    warnings: [],
  });
  mockGetSectorPerformance.mockResolvedValue({
    data: [
      { sector: "Technology", total_pnl: 2000, total_pnl_pct: 12.5, position_count: 3, best_ticker: "AAPL", worst_ticker: "INTC" },
      { sector: "Automotive", total_pnl: -500, total_pnl_pct: -8.3, position_count: 1, best_ticker: null, worst_ticker: "TSLA" },
    ] as never,
    warnings: [],
  });
  mockCompareSnapshots.mockResolvedValue({
    data: {
      date_a: "2025-01-01",
      date_b: "2025-06-01",
      total_value_a: 100000,
      total_value_b: 115000,
      value_change: 15000,
      value_change_pct: 15.0,
      positions_added: ["GOOG"],
      positions_removed: ["META"],
      positions_changed: [
        { ticker: "AAPL", value_a: 50000, value_b: 55000, change_pct: 10.0 },
      ],
    } as never,
    warnings: [],
  });
  mockGetReturns.mockResolvedValue({
    data: {
      aggregate: {
        ttwror: 12.34,
        irr: 9.87,
        snapshot_count: 45,
        start_value: 100000,
        end_value: 112340,
        window_days: 365,
      },
      positions: [],
    } as never,
    warnings: [],
  });
  mockGetDailyPnl.mockResolvedValue({ data: [] as never, warnings: [] });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <PerformancePage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("PerformancePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
  });

  it("renders skeleton components while loading", () => {
    mockGetValueHistory.mockReturnValue(new Promise(() => {}));
    mockGetPerformanceSummary.mockReturnValue(new Promise(() => {}));
    mockGetMonthlyReturns.mockReturnValue(new Promise(() => {}));
    mockGetTopPerformers.mockReturnValue(new Promise(() => {}));
    mockGetBenchmarkComparison.mockReturnValue(new Promise(() => {}));
    mockGetCumulativePnl.mockReturnValue(new Promise(() => {}));
    mockGetDrawdownSeries.mockReturnValue(new Promise(() => {}));
    mockGetRollingSharpe.mockReturnValue(new Promise(() => {}));
    mockGetMonthlyHeatmap.mockReturnValue(new Promise(() => {}));
    mockGetPerformanceAttribution.mockReturnValue(new Promise(() => {}));
    mockGetSectorPerformance.mockReturnValue(new Promise(() => {}));
    mockCompareSnapshots.mockReturnValue(new Promise(() => {}));
    mockGetReturns.mockReturnValue(new Promise(() => {}));
    mockGetDailyPnl.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error alert when API rejects", async () => {
    mockGetValueHistory.mockRejectedValue(new Error("Server unavailable"));
    mockGetPerformanceSummary.mockRejectedValue(new Error("Server unavailable"));
    mockGetMonthlyReturns.mockRejectedValue(new Error("Server unavailable"));
    mockGetTopPerformers.mockRejectedValue(new Error("Server unavailable"));
    mockGetBenchmarkComparison.mockRejectedValue(new Error("Server unavailable"));
    mockGetCumulativePnl.mockRejectedValue(new Error("Server unavailable"));
    mockGetDrawdownSeries.mockRejectedValue(new Error("Server unavailable"));
    mockGetRollingSharpe.mockRejectedValue(new Error("Server unavailable"));
    mockGetMonthlyHeatmap.mockRejectedValue(new Error("Server unavailable"));
    mockGetPerformanceAttribution.mockRejectedValue(new Error("Server unavailable"));
    mockGetSectorPerformance.mockRejectedValue(new Error("Server unavailable"));
    mockCompareSnapshots.mockRejectedValue(new Error("Server unavailable"));
    mockGetReturns.mockRejectedValue(new Error("Server unavailable"));
    mockGetDailyPnl.mockRejectedValue(new Error("Server unavailable"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it('renders "Performance" heading when data loads', async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Performance")).toBeInTheDocument();
    });
  });

  it("renders performance metric cards", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Total P&L")).toBeInTheDocument();
    });
    expect(screen.getByText("Win Rate")).toBeInTheDocument();
    expect(screen.getByText("Avg Win")).toBeInTheDocument();
    expect(screen.getByText("Avg Loss")).toBeInTheDocument();
    expect(screen.getByText("Total Trades")).toBeInTheDocument();
  });

  it("renders total trades count from summary data", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("11")).toBeInTheDocument();
    });
    expect(screen.getByText("11 trades")).toBeInTheDocument();
  });

  it("renders monthly returns section", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Monthly Returns")).toBeInTheDocument();
    });
  });

  it("renders top performers section", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Top Performers")).toBeInTheDocument();
    });
  });

  it("renders drawdown chart section", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Drawdown")).toBeInTheDocument();
    });
  });

  it("renders rolling sharpe chart section", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Rolling Sharpe Ratio")).toBeInTheDocument();
    });
  });

  it("renders monthly heatmap section", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Monthly Returns Heatmap")).toBeInTheDocument();
    });
  });

  it("renders P&L Attribution section", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("P&L Attribution")).toBeInTheDocument();
    });
  });

  it("calls new analytics endpoints", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(mockGetDrawdownSeries).toHaveBeenCalled();
    });
    expect(mockGetRollingSharpe).toHaveBeenCalled();
    expect(mockGetMonthlyHeatmap).toHaveBeenCalled();
  });

  it("renders Portfolio Snapshot Comparison section", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText("Portfolio Snapshot Comparison"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Compare")).toBeInTheDocument();
  });

  it("renders Sector Performance section", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Sector Performance")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Technology").length).toBeGreaterThan(0);
  });

  // Phase 04-03: UI-01 TTWROR card
  it("displays TTWROR value from getReturns API", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("ttwror-value")).toBeInTheDocument();
    });
    expect(screen.getByTestId("ttwror-value")).toHaveTextContent("+12.34%");
  });

  it("displays IRR value from getReturns API", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("irr-value")).toBeInTheDocument();
    });
    expect(screen.getByTestId("irr-value")).toHaveTextContent("+9.87%");
  });

  // Phase 04-03: UI-02 BenchmarkSelector
  it("renders BenchmarkSelector dropdown with 5 options", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("benchmark-selector")).toBeInTheDocument();
    });
    const select = screen.getByTestId("benchmark-selector") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual([
      "SPY", "QQQ", "TLT", "GLD", "BTC-USD",
    ]);
  });

  it("changing benchmark selector triggers getBenchmarkComparison with new ticker", async () => {
    const user = userEvent.setup();
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("benchmark-selector")).toBeInTheDocument();
    });
    await user.selectOptions(screen.getByTestId("benchmark-selector"), "QQQ");
    await waitFor(() => {
      expect(mockGetBenchmarkComparison).toHaveBeenCalledWith(90, "QQQ");
    });
  });

  // Phase 04-03: UI-05 DailyPnlHeatmap
  it("renders DailyPnlHeatmap section", async () => {
    mockAllApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Daily P&L Heatmap")).toBeInTheDocument();
    });
  });
});
