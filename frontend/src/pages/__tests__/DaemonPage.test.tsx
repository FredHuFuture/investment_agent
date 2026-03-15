import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock ALL endpoint functions imported by DaemonPage
vi.mock("../../api/endpoints", () => ({
  getDaemonStatus: vi.fn(),
  daemonRunOnce: vi.fn(),
}));

import { getDaemonStatus, daemonRunOnce } from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import DaemonPage from "../DaemonPage";

const mockGetDaemonStatus = vi.mocked(getDaemonStatus);
const mockDaemonRunOnce = vi.mocked(daemonRunOnce);

const mockDaemonData = {
  daily_check: { last_run: "2024-06-01T17:00:00Z", status: "success" },
  weekly_revaluation: { last_run: "2024-06-01T10:00:00Z", status: "success" },
  catalyst_scan: { last_run: null, status: "disabled" },
  regime_detection: { last_run: "2024-06-01T12:00:00Z", status: "success" },
  watchlist_scan: { last_run: "2024-06-01T14:00:00Z", status: "success" },
};

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <DaemonPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("DaemonPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
  });

  it("renders skeleton components while loading", () => {
    mockGetDaemonStatus.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error alert when API rejects", async () => {
    mockGetDaemonStatus.mockRejectedValue(new Error("Server unavailable"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it('renders "Daemon" heading when data loads', async () => {
    mockGetDaemonStatus.mockResolvedValue({
      data: mockDaemonData as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Daemon")).toBeInTheDocument();
    });
  });

  it("renders all 5 daemon job cards with status", async () => {
    mockGetDaemonStatus.mockResolvedValue({
      data: mockDaemonData as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Daily Check")).toBeInTheDocument();
    });
    expect(screen.getByText("Weekly Revaluation")).toBeInTheDocument();
    expect(screen.getByText("Catalyst Scan")).toBeInTheDocument();
    expect(screen.getByText("Regime Detection")).toBeInTheDocument();
    expect(screen.getByText("Watchlist Scan")).toBeInTheDocument();
  });

  it("renders empty state when no jobs configured", async () => {
    mockGetDaemonStatus.mockResolvedValue({
      data: {} as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("No daemon jobs configured.")).toBeInTheDocument();
    });
  });

  it("renders run buttons for all triggerable jobs", async () => {
    mockGetDaemonStatus.mockResolvedValue({
      data: mockDaemonData as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Run Daily Check")).toBeInTheDocument();
    });
    expect(screen.getByText("Run Weekly Revaluation")).toBeInTheDocument();
    expect(screen.getByText("Run Regime Detection")).toBeInTheDocument();
    expect(screen.getByText("Run Watchlist Scan")).toBeInTheDocument();
  });

  it("renders disabled placeholder for catalyst scan", async () => {
    mockGetDaemonStatus.mockResolvedValue({
      data: mockDaemonData as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Requires LLM (Task 023)")).toBeInTheDocument();
    });
  });

  it("calls daemonRunOnce with 'regime' when regime button clicked", async () => {
    mockGetDaemonStatus.mockResolvedValue({
      data: mockDaemonData as never,
      warnings: [],
    });
    mockDaemonRunOnce.mockResolvedValue({ data: {} as never, warnings: [] });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Run Regime Detection")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByText("Run Regime Detection"));

    await waitFor(() => {
      expect(mockDaemonRunOnce).toHaveBeenCalledWith("regime");
    });
  });

  it("calls daemonRunOnce with 'watchlist' when watchlist button clicked", async () => {
    mockGetDaemonStatus.mockResolvedValue({
      data: mockDaemonData as never,
      warnings: [],
    });
    mockDaemonRunOnce.mockResolvedValue({ data: {} as never, warnings: [] });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Run Watchlist Scan")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByText("Run Watchlist Scan"));

    await waitFor(() => {
      expect(mockDaemonRunOnce).toHaveBeenCalledWith("watchlist");
    });
  });
});
