import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock ALL endpoint functions imported by JournalPage
vi.mock("../../api/endpoints", () => ({
  getPositionHistory: vi.fn(),
  getPerformanceSummary: vi.fn(),
}));

import {
  getPositionHistory,
  getPerformanceSummary,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import JournalPage from "../JournalPage";

const mockGetPositionHistory = vi.mocked(getPositionHistory);
const mockGetPerformanceSummary = vi.mocked(getPerformanceSummary);

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
      expect(screen.getByText("No closed trades yet.")).toBeInTheDocument();
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
});
