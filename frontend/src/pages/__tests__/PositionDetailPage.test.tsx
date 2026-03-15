import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import React from "react";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock recharts to avoid canvas/SVG issues in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
  LineChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "line-chart" }, children),
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
}));

// Mock ALL endpoint functions imported by PositionDetailPage and its children
vi.mock("../../api/endpoints", () => ({
  getPortfolio: vi.fn(),
  getPositionHistory: vi.fn(),
  getThesis: vi.fn(),
  getPriceHistory: vi.fn(),
  getSignalHistory: vi.fn(),
  getAlerts: vi.fn(),
  updateThesis: vi.fn(),
  getCatalysts: vi.fn(),
  getPositionPnlHistory: vi.fn(),
}));

import {
  getPortfolio,
  getPositionHistory,
  getThesis,
  getPriceHistory,
  getSignalHistory,
  getAlerts,
  getCatalysts,
  getPositionPnlHistory,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import PositionDetailPage from "../PositionDetailPage";

const mockGetPortfolio = vi.mocked(getPortfolio);
const mockGetPositionHistory = vi.mocked(getPositionHistory);
const mockGetThesis = vi.mocked(getThesis);
const mockGetPriceHistory = vi.mocked(getPriceHistory);
const mockGetSignalHistory = vi.mocked(getSignalHistory);
const mockGetAlerts = vi.mocked(getAlerts);
const mockGetCatalysts = vi.mocked(getCatalysts);
const mockGetPositionPnlHistory = vi.mocked(getPositionPnlHistory);

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
      thesis_text: "Strong momentum",
      expected_return_pct: 0.2,
      expected_hold_days: 90,
      target_price: 200,
      stop_loss: 130,
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
  mockGetPositionHistory.mockResolvedValue({ data: [], warnings: [] });
  mockGetThesis.mockResolvedValue({
    data: {
      ticker: "AAPL",
      thesis_text: "Strong momentum",
      expected_return_pct: 0.2,
      expected_hold_days: 90,
      target_price: 200,
      stop_loss: 130,
      hold_days_elapsed: 30,
      hold_drift_days: null,
      return_drift_pct: null,
    } as never,
    warnings: [],
  });
  mockGetPriceHistory.mockResolvedValue({ data: [], warnings: [] });
  mockGetSignalHistory.mockResolvedValue({ data: [], warnings: [] });
  mockGetAlerts.mockResolvedValue({ data: [], warnings: [] });
  mockGetCatalysts.mockRejectedValue(new Error("Not available"));
  mockGetPositionPnlHistory.mockResolvedValue({ data: [] as never, warnings: [] });
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/positions/AAPL"]}>
      <Routes>
        <Route
          path="/positions/:ticker"
          element={
            <ToastProvider>
              <PositionDetailPage />
            </ToastProvider>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("PositionDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
  });

  it("renders skeleton while loading", () => {
    mockGetPortfolio.mockReturnValue(new Promise(() => {}));
    mockSecondaryApis();
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error alert when getPortfolio rejects", async () => {
    mockGetPortfolio.mockRejectedValue(new Error("Server unavailable"));
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders position ticker heading when data loads", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "AAPL" })).toBeInTheDocument();
    });
  });

  it("renders position metrics (cost basis, market value, P&L)", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Cost Basis")).toBeInTheDocument();
    });
    expect(screen.getByText("$1,500")).toBeInTheDocument();
    expect(screen.getByText("Current Value")).toBeInTheDocument();
    expect(screen.getByText("$1,700")).toBeInTheDocument();
    expect(screen.getByText("Unrealized P&L")).toBeInTheDocument();
  });

  it("renders empty state when position not found", async () => {
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
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText(/Position "AAPL" not found/),
      ).toBeInTheDocument();
    });
  });

  it("renders breadcrumb with ticker", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Portfolio")).toBeInTheDocument();
    });
  });
});
