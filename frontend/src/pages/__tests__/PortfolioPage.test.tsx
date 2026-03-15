import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock ALL endpoint functions imported by PortfolioPage and its children
vi.mock("../../api/endpoints", () => ({
  getPortfolio: vi.fn(),
  getAlerts: vi.fn(),
  getPositionHistory: vi.fn(),
  addPosition: vi.fn(),
  removePosition: vi.fn(),
  closePosition: vi.fn(),
  setCash: vi.fn(),
  scalePortfolio: vi.fn(),
  acknowledgeAlert: vi.fn(),
  deleteAlert: vi.fn(),
  getLatestSummary: vi.fn(),
  generateSummary: vi.fn(),
  updateThesis: vi.fn(),
  listProfiles: vi.fn(),
  createProfile: vi.fn(),
  updateProfile: vi.fn(),
  deleteProfile: vi.fn(),
  setDefaultProfile: vi.fn(),
  bulkImportPositions: vi.fn(),
  getPortfolioGoals: vi.fn(),
  addPortfolioGoal: vi.fn(),
  deletePortfolioGoal: vi.fn(),
}));

import {
  getPortfolio,
  getAlerts,
  getPositionHistory,
  getLatestSummary,
  listProfiles,
  getPortfolioGoals,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import PortfolioPage from "../PortfolioPage";

const mockGetPortfolio = vi.mocked(getPortfolio);
const mockGetAlerts = vi.mocked(getAlerts);
const mockGetPositionHistory = vi.mocked(getPositionHistory);
const mockGetLatestSummary = vi.mocked(getLatestSummary);
const mockListProfiles = vi.mocked(listProfiles);
const mockGetPortfolioGoals = vi.mocked(getPortfolioGoals);

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
    {
      ticker: "MSFT",
      asset_type: "stock",
      quantity: 5,
      avg_cost: 300,
      current_price: 350,
      entry_date: "2024-02-01",
      sector: "Tech",
      industry: null,
      cost_basis: 1500,
      market_value: 1750,
      unrealized_pnl: 250,
      unrealized_pnl_pct: 0.167,
      holding_days: 15,
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
  total_value: 53450,
  stock_exposure_pct: 0.064,
  crypto_exposure_pct: 0,
  cash_pct: 0.936,
  sector_breakdown: { Tech: 0.064 },
  top_concentration: [
    ["AAPL", 0.032],
    ["MSFT", 0.033],
  ],
};

const mockDefaultProfile = {
  id: 1,
  name: "Default",
  description: "",
  cash: 50000,
  created_at: "2024-01-01T00:00:00Z",
  is_default: 1,
};

function mockSecondaryApis() {
  mockGetAlerts.mockResolvedValue({ data: [], warnings: [] });
  mockGetPositionHistory.mockResolvedValue({ data: [], warnings: [] });
  mockGetLatestSummary.mockRejectedValue({ status: 404, message: "Not found" });
  mockListProfiles.mockResolvedValue({ data: [mockDefaultProfile as never], warnings: [] });
  mockGetPortfolioGoals.mockResolvedValue({
    data: [
      { id: 1, label: "Retirement Fund", target_value: 100000, target_date: "2030-01-01", created_at: "2024-01-01T00:00:00" },
    ],
    warnings: [],
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <PortfolioPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("PortfolioPage", () => {
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
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
  });

  it("renders error alert with retry when API rejects", async () => {
    mockGetPortfolio.mockRejectedValue(new Error("Connection refused"));
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Connection refused")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders positions table with ticker names", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("AAPL").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("MSFT").length).toBeGreaterThan(0);
  });

  it("renders search placeholder on positions table", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search by ticker/i)).toBeInTheDocument();
    });
  });

  it("renders cash balance in metric card", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Portfolio Value")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Cash").length).toBeGreaterThan(0);
    expect(screen.getByText("$50,000")).toBeInTheDocument();
  });

  it("renders Import CSV button", async () => {
    mockGetPortfolio.mockResolvedValue({
      data: mockPortfolio as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Import CSV")).toBeInTheDocument();
    });
  });

  it("renders Goal Tracker with goals", async () => {
    mockGetPortfolio.mockResolvedValue({ data: mockPortfolio as never, warnings: [] });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Retirement Fund")).toBeInTheDocument();
    });
    expect(screen.getByText("Portfolio Goals")).toBeInTheDocument();
  });
});
