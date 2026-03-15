import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock recharts to avoid canvas/SVG issues in jsdom
vi.mock("recharts", () => ({
  BarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "bar-chart" }, children),
  Bar: () => null,
  AreaChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "area-chart" }, children),
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
  CartesianGrid: () => null,
  ReferenceLine: () => null,
  Cell: () => null,
}));

// Mock ALL endpoint functions imported by JournalPage
vi.mock("../../api/endpoints", () => ({
  getPositionHistory: vi.fn(),
  getPerformanceSummary: vi.fn(),
  getTradeAnnotations: vi.fn(),
  createTradeAnnotation: vi.fn(),
  getLessonTagStats: vi.fn(),
}));

import {
  getPositionHistory,
  getPerformanceSummary,
  getTradeAnnotations,
  createTradeAnnotation,
  getLessonTagStats,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import JournalPage from "../JournalPage";

const mockGetPositionHistory = vi.mocked(getPositionHistory);
const mockGetPerformanceSummary = vi.mocked(getPerformanceSummary);
const mockGetTradeAnnotations = vi.mocked(getTradeAnnotations);
const mockCreateTradeAnnotation = vi.mocked(createTradeAnnotation);
const mockGetLessonTagStats = vi.mocked(getLessonTagStats);

const mockClosedPosition = {
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
  status: "closed",
  exit_price: 170,
  exit_date: "2024-03-01",
  exit_reason: "target_hit",
  realized_pnl: 200,
};

const mockPerformanceSummary = {
  total_trades: 5,
  win_count: 3,
  loss_count: 2,
  win_rate: 60.0,
  avg_win_pct: 12.5,
  avg_loss_pct: -5.2,
  avg_hold_days: 25,
  total_realized_pnl: 1500,
  best_trade: { ticker: "AAPL", return_pct: 13.3, pnl: 200 },
  worst_trade: { ticker: "TSLA", return_pct: -8.0, pnl: -400 },
  profit_factor: 1.85,
  expectancy: 5.2,
  max_consecutive_wins: 3,
  max_consecutive_losses: 1,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <JournalPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("JournalPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
    // Default: annotations endpoint returns empty for any ticker
    mockGetTradeAnnotations.mockResolvedValue({
      data: [] as never,
      warnings: [],
    });
    mockCreateTradeAnnotation.mockResolvedValue({
      data: {
        id: 1,
        position_ticker: "AAPL",
        annotation_text: "test",
        lesson_tag: null,
        created_at: "2024-03-01 00:00:00",
      } as never,
      warnings: [],
    });
    mockGetLessonTagStats.mockResolvedValue({
      data: [] as never,
      warnings: [],
    });
  });

  it("renders skeleton while loading", () => {
    mockGetPositionHistory.mockReturnValue(new Promise(() => {}));
    mockGetPerformanceSummary.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error alert when API rejects", async () => {
    mockGetPositionHistory.mockRejectedValue(new Error("Server unavailable"));
    mockGetPerformanceSummary.mockRejectedValue(new Error("Server unavailable"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders 'Trade Journal' heading when data loads", async () => {
    mockGetPositionHistory.mockResolvedValue({
      data: [mockClosedPosition] as never,
      warnings: [],
    });
    mockGetPerformanceSummary.mockResolvedValue({
      data: mockPerformanceSummary as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Trade Journal")).toBeInTheDocument();
    });
  });

  it("renders closed trades data", async () => {
    mockGetPositionHistory.mockResolvedValue({
      data: [mockClosedPosition] as never,
      warnings: [],
    });
    mockGetPerformanceSummary.mockResolvedValue({
      data: mockPerformanceSummary as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      // AAPL appears in both Best Trade card and the data table
      const aaplElements = screen.getAllByText("AAPL");
      expect(aaplElements.length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("Closed Positions")).toBeInTheDocument();
  });

  it("renders empty state when no closed trades", async () => {
    mockGetPositionHistory.mockResolvedValue({
      data: [] as never,
      warnings: [],
    });
    mockGetPerformanceSummary.mockResolvedValue({
      data: mockPerformanceSummary as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      // Multiple empty states (charts + table) all show this message
      const emptyTexts = screen.getAllByText("No closed trades yet.");
      expect(emptyTexts.length).toBeGreaterThan(0);
    });
  });

  it("renders performance summary metrics", async () => {
    mockGetPositionHistory.mockResolvedValue({
      data: [mockClosedPosition] as never,
      warnings: [],
    });
    mockGetPerformanceSummary.mockResolvedValue({
      data: mockPerformanceSummary as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Total Trades")).toBeInTheDocument();
    });
    expect(screen.getByText("Win Rate")).toBeInTheDocument();
  });

  it("renders lesson summary section when trades exist", async () => {
    mockGetPositionHistory.mockResolvedValue({
      data: [mockClosedPosition] as never,
      warnings: [],
    });
    mockGetPerformanceSummary.mockResolvedValue({
      data: mockPerformanceSummary as never,
      warnings: [],
    });
    mockGetTradeAnnotations.mockResolvedValue({
      data: [
        {
          id: 1,
          position_ticker: "AAPL",
          annotation_text: "Good entry timing",
          lesson_tag: "entry_timing",
          created_at: "2024-03-01 12:00:00",
        },
      ] as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Lesson Summary")).toBeInTheDocument();
    });
  });

  it("fetches annotations for closed position tickers", async () => {
    mockGetPositionHistory.mockResolvedValue({
      data: [mockClosedPosition] as never,
      warnings: [],
    });
    mockGetPerformanceSummary.mockResolvedValue({
      data: mockPerformanceSummary as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(mockGetTradeAnnotations).toHaveBeenCalledWith("AAPL");
    });
  });

  it("renders LessonAnalytics when tag stats are available", async () => {
    mockGetPositionHistory.mockResolvedValue({
      data: [mockClosedPosition] as never,
      warnings: [],
    });
    mockGetPerformanceSummary.mockResolvedValue({
      data: mockPerformanceSummary as never,
      warnings: [],
    });
    mockGetLessonTagStats.mockResolvedValue({
      data: [
        {
          tag: "entry_timing",
          count: 5,
          win_count: 3,
          loss_count: 2,
          win_rate: 60.0,
          avg_return_pct: 4.5,
        },
        {
          tag: "position_sizing",
          count: 3,
          win_count: 1,
          loss_count: 2,
          win_rate: 33.3,
          avg_return_pct: -2.1,
        },
      ] as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Lesson Tag Analytics")).toBeInTheDocument();
    });
    expect(screen.getByText("Entry Timing")).toBeInTheDocument();
    expect(screen.getByText("Position Sizing")).toBeInTheDocument();
  });

  it("renders pattern alert for low win-rate tags", async () => {
    mockGetPositionHistory.mockResolvedValue({
      data: [mockClosedPosition] as never,
      warnings: [],
    });
    mockGetPerformanceSummary.mockResolvedValue({
      data: mockPerformanceSummary as never,
      warnings: [],
    });
    mockGetLessonTagStats.mockResolvedValue({
      data: [
        {
          tag: "emotional",
          count: 4,
          win_count: 1,
          loss_count: 3,
          win_rate: 25.0,
          avg_return_pct: -8.5,
        },
      ] as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/consider reviewing this pattern/)).toBeInTheDocument();
    });
  });
});
