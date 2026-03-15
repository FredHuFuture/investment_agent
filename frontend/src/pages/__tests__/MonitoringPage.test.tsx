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
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
  Legend: () => null,
}));

// Mock the API endpoints module -- vi.mock is hoisted above imports
vi.mock("../../api/endpoints", () => ({
  getAlerts: vi.fn(),
  runMonitorCheck: vi.fn(),
  acknowledgeAlert: vi.fn(),
  deleteAlert: vi.fn(),
  batchAcknowledgeAlerts: vi.fn(),
  getAlertTimeline: vi.fn(),
  getAlertStats: vi.fn(),
}));

import { getAlerts, getAlertTimeline, getAlertStats } from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import MonitoringPage from "../MonitoringPage";

const mockGetAlerts = vi.mocked(getAlerts);
const mockGetAlertTimeline = vi.mocked(getAlertTimeline);
const mockGetAlertStats = vi.mocked(getAlertStats);

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <MonitoringPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("MonitoringPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
    // Default: timeline returns empty
    mockGetAlertTimeline.mockResolvedValue({ data: [], warnings: [] });
    // Default: alert stats returns zeros
    mockGetAlertStats.mockResolvedValue({
      data: {
        total_count: 0,
        unacknowledged_count: 0,
        ack_rate_pct: 100,
        by_ticker: [],
        by_type: {},
        by_severity: {},
        avg_alerts_per_day: 0,
      },
      warnings: [],
    });
  });

  it("renders skeleton while loading", () => {
    mockGetAlerts.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error message when API rejects", async () => {
    mockGetAlerts.mockRejectedValue(new Error("Network error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("renders alerts when data is returned", async () => {
    mockGetAlerts.mockResolvedValue({
      data: [
        {
          id: 1,
          ticker: "AAPL",
          alert_type: "PRICE_DROP",
          severity: "HIGH",
          message: "Price dropped 5%",
          acknowledged: 0,
          created_at: "2024-06-01T12:00:00Z",
        },
        {
          id: 2,
          ticker: "TSLA",
          alert_type: "VOLUME_SPIKE",
          severity: "WARNING",
          message: "Volume spike detected",
          acknowledged: 0,
          created_at: "2024-06-01T13:00:00Z",
        },
      ],
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Monitoring")).toBeInTheDocument();
    });
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
  });

  it("renders empty state when no alerts exist", async () => {
    mockGetAlerts.mockResolvedValue({ data: [], warnings: [] });
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText(
          "No alerts. Run a health check to generate alerts.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("renders severity summary chips when alerts have different severities", async () => {
    mockGetAlerts.mockResolvedValue({
      data: [
        {
          id: 1,
          ticker: "AAPL",
          alert_type: "PRICE_DROP",
          severity: "CRITICAL",
          message: "Critical alert",
          acknowledged: 0,
          created_at: "2024-06-01T12:00:00Z",
        },
        {
          id: 2,
          ticker: "TSLA",
          alert_type: "VOLUME_SPIKE",
          severity: "CRITICAL",
          message: "Another critical",
          acknowledged: 0,
          created_at: "2024-06-01T13:00:00Z",
        },
        {
          id: 3,
          ticker: "GOOG",
          alert_type: "INFO",
          severity: "INFO",
          message: "Info alert",
          acknowledged: 1,
          created_at: "2024-06-01T14:00:00Z",
        },
      ],
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/2 Critical/)).toBeInTheDocument();
      expect(screen.getByText(/1 Info/)).toBeInTheDocument();
    });
  });

  it("renders severity filter bar with pill buttons", async () => {
    mockGetAlerts.mockResolvedValue({ data: [], warnings: [] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Critical")).toBeInTheDocument();
      expect(screen.getByText("High")).toBeInTheDocument();
      expect(screen.getByText("Warning")).toBeInTheDocument();
      expect(screen.getByText("Low")).toBeInTheDocument();
      expect(screen.getByText("Info")).toBeInTheDocument();
    });
  });
});
