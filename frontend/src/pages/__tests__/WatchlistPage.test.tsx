import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock ALL endpoint functions imported by WatchlistPage
vi.mock("../../api/endpoints", () => ({
  getWatchlist: vi.fn(),
  addToWatchlist: vi.fn(),
  removeFromWatchlist: vi.fn(),
  analyzeWatchlistTicker: vi.fn(),
  analyzeAllWatchlist: vi.fn(),
  updateWatchlistItem: vi.fn(),
}));

import { getWatchlist } from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import WatchlistPage from "../WatchlistPage";

const mockGetWatchlist = vi.mocked(getWatchlist);

const mockWatchlistItem = {
  id: 1,
  ticker: "AAPL",
  asset_type: "stock",
  notes: "",
  target_buy_price: null,
  alert_below_price: null,
  added_at: "2024-01-01T00:00:00Z",
  last_analysis_at: null,
  last_signal: null,
  last_confidence: null,
};

const mockWatchlistItems = [
  mockWatchlistItem,
  {
    id: 2,
    ticker: "MSFT",
    asset_type: "stock",
    notes: "Cloud growth",
    target_buy_price: 350,
    alert_below_price: null,
    added_at: "2024-01-02T00:00:00Z",
    last_analysis_at: null,
    last_signal: null,
    last_confidence: null,
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <WatchlistPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("WatchlistPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
  });

  it("renders skeleton while loading", () => {
    mockGetWatchlist.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders 'Watchlist' heading when data loads", async () => {
    mockGetWatchlist.mockResolvedValue({
      data: mockWatchlistItems as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Watchlist")).toBeInTheDocument();
    });
  });

  it("renders watchlist items", async () => {
    mockGetWatchlist.mockResolvedValue({
      data: mockWatchlistItems as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    expect(screen.getByText("MSFT")).toBeInTheDocument();
  });

  it("renders empty state when no items", async () => {
    mockGetWatchlist.mockResolvedValue({
      data: [] as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText("No tickers on your watchlist yet. Add one above."),
      ).toBeInTheDocument();
    });
  });

  it("renders 'Watchlist' heading even with empty data", async () => {
    mockGetWatchlist.mockResolvedValue({
      data: [] as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Watchlist")).toBeInTheDocument();
    });
    expect(
      screen.getByText("No tickers on your watchlist yet. Add one above."),
    ).toBeInTheDocument();
  });

  it("renders add ticker form", async () => {
    mockGetWatchlist.mockResolvedValue({
      data: [] as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Add Ticker")).toBeInTheDocument();
    });
  });

  it("renders action buttons for watchlist items", async () => {
    mockGetWatchlist.mockResolvedValue({
      data: [mockWatchlistItem] as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    expect(screen.getByText("Edit")).toBeInTheDocument();
    expect(screen.getByText("Analyze")).toBeInTheDocument();
    expect(screen.getByText("Remove")).toBeInTheDocument();
  });
});
