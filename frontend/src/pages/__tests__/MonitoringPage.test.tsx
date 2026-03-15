import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock the API endpoints module -- vi.mock is hoisted above imports
vi.mock("../../api/endpoints", () => ({
  getAlerts: vi.fn(),
  runMonitorCheck: vi.fn(),
  acknowledgeAlert: vi.fn(),
  deleteAlert: vi.fn(),
}));

import { getAlerts } from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import MonitoringPage from "../MonitoringPage";

const mockGetAlerts = vi.mocked(getAlerts);

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
          severity: "high",
          message: "Price dropped 5%",
          acknowledged: 0,
          created_at: "2024-06-01T12:00:00Z",
        },
        {
          id: 2,
          ticker: "TSLA",
          alert_type: "VOLUME_SPIKE",
          severity: "medium",
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
});
