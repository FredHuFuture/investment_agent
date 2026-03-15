import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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
}));

// Mock ALL endpoint functions imported by PerformancePage
vi.mock("../../api/endpoints", () => ({
  getValueHistory: vi.fn(),
  getPerformanceSummary: vi.fn(),
  getMonthlyReturns: vi.fn(),
  getTopPerformers: vi.fn(),
  getBenchmarkComparison: vi.fn(),
}));

import {
  getValueHistory,
  getPerformanceSummary,
  getMonthlyReturns,
  getTopPerformers,
  getBenchmarkComparison,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import PerformancePage from "../PerformancePage";

const mockGetValueHistory = vi.mocked(getValueHistory);
const mockGetPerformanceSummary = vi.mocked(getPerformanceSummary);
const mockGetMonthlyReturns = vi.mocked(getMonthlyReturns);
const mockGetTopPerformers = vi.mocked(getTopPerformers);
const mockGetBenchmarkComparison = vi.mocked(getBenchmarkComparison);

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
      series: [],
    } as never,
    warnings: [],
  });
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
});
