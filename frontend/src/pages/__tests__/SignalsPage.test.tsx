import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock recharts (CalibrationChart uses it)
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
  BarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "bar-chart" }, children),
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
}));

// Mock ALL endpoint functions imported by SignalsPage and its children
vi.mock("../../api/endpoints", () => ({
  getSignalHistory: vi.fn(),
  getAccuracyStats: vi.fn(),
  getCalibration: vi.fn(),
  getAgentPerformance: vi.fn(),
}));

import {
  getSignalHistory,
  getAccuracyStats,
  getCalibration,
  getAgentPerformance,
} from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import SignalsPage from "../SignalsPage";

const mockGetSignalHistory = vi.mocked(getSignalHistory);
const mockGetAccuracyStats = vi.mocked(getAccuracyStats);
const mockGetCalibration = vi.mocked(getCalibration);
const mockGetAgentPerformance = vi.mocked(getAgentPerformance);

const mockSignalEntries = [
  {
    id: 1,
    ticker: "AAPL",
    final_signal: "BUY",
    final_confidence: 75,
    raw_score: 0.5,
    consensus_score: 0.6,
    regime: null,
    agent_signals: [],
    reasoning: "test",
    created_at: "2024-01-01T00:00:00Z",
  },
  {
    id: 2,
    ticker: "MSFT",
    final_signal: "SELL",
    final_confidence: 60,
    raw_score: -0.3,
    consensus_score: -0.4,
    regime: null,
    agent_signals: [],
    reasoning: "test2",
    created_at: "2024-01-02T00:00:00Z",
  },
];

/** Set up all secondary API mocks with reasonable defaults */
function mockSecondaryApis() {
  mockGetAccuracyStats.mockResolvedValue({
    data: { total: 0, correct: 0, accuracy: 0 } as never,
    warnings: [],
  });
  mockGetCalibration.mockResolvedValue({ data: [], warnings: [] });
  mockGetAgentPerformance.mockResolvedValue({ data: {} as never, warnings: [] });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <SignalsPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("SignalsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
  });

  it("renders skeleton while loading", () => {
    mockGetSignalHistory.mockReturnValue(new Promise(() => {}));
    mockSecondaryApis();
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error alert when API rejects", async () => {
    mockGetSignalHistory.mockRejectedValue(new Error("Server unavailable"));
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders 'Signals' heading when data loads", async () => {
    mockGetSignalHistory.mockResolvedValue({
      data: mockSignalEntries as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Signals")).toBeInTheDocument();
    });
  });

  it("renders signal history entries", async () => {
    mockGetSignalHistory.mockResolvedValue({
      data: mockSignalEntries as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    expect(screen.getByText("MSFT")).toBeInTheDocument();
  });

  it("renders empty state when history returns empty array", async () => {
    mockGetSignalHistory.mockResolvedValue({ data: [] as never, warnings: [] });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No signal history.")).toBeInTheDocument();
    });
  });

  it("renders 'Signals' heading even with empty data", async () => {
    mockGetSignalHistory.mockResolvedValue({ data: [] as never, warnings: [] });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Signals")).toBeInTheDocument();
    });
    expect(screen.getByText("No signal history.")).toBeInTheDocument();
  });

  it("renders BUY signal badge for first entry", async () => {
    mockGetSignalHistory.mockResolvedValue({
      data: mockSignalEntries as never,
      warnings: [],
    });
    mockSecondaryApis();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
    });
    // BUY appears both in the filter dropdown and as a signal badge
    const buyElements = screen.getAllByText("BUY");
    expect(buyElements.length).toBeGreaterThanOrEqual(2);
  });
});
