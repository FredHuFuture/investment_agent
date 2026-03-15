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
}));

// Mock ALL endpoint functions imported by DashboardPage and its children
vi.mock("../../api/endpoints", () => ({
  getPortfolio: vi.fn(),
  getAlerts: vi.fn(),
  getPositionHistory: vi.fn(),
  getValueHistory: vi.fn(),
  getWatchlist: vi.fn(),
  getRegime: vi.fn(),
  runMonitorCheck: vi.fn(),
  getLatestSummary: vi.fn(),
  generateSummary: vi.fn(),
}));

import {
  getPortfolio,
  getAlerts,
  getPositionHistory,
  getValueHistory,
  getWatchlist,
  getRegime,
  getLatestSummary,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import DashboardPage from "../DashboardPage";

const mockGetPortfolio = vi.mocked(getPortfolio);
const mockGetAlerts = vi.mocked(getAlerts);
const mockGetPositionHistory = vi.mocked(getPositionHistory);
const mockGetValueHistory = vi.mocked(getValueHistory);
const mockGetWatchlist = vi.mocked(getWatchlist);
const mockGetRegime = vi.mocked(getRegime);
const mockGetLatestSummary = vi.mocked(getLatestSummary);

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
  // WeeklySummaryCard calls getLatestSummary directly (not via useApi)
  mockGetLatestSummary.mockRejectedValue({ status: 404, message: "Not found" });
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
});
