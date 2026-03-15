import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock ALL endpoint functions imported by DaemonPage
vi.mock("../../api/endpoints", () => ({
  getDaemonStatus: vi.fn(),
  daemonRunOnce: vi.fn(),
}));

import { getDaemonStatus } from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import DaemonPage from "../DaemonPage";

const mockGetDaemonStatus = vi.mocked(getDaemonStatus);

const mockDaemonData = {
  daily_check: { last_run: "2024-06-01T17:00:00Z", status: "success" },
  weekly_revaluation: { last_run: "2024-06-01T10:00:00Z", status: "success" },
  catalyst_scan: { last_run: null, status: "disabled" },
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

  it("renders daemon job cards with status", async () => {
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

  it("renders run buttons for triggerable jobs", async () => {
    mockGetDaemonStatus.mockResolvedValue({
      data: mockDaemonData as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Run Daily Check")).toBeInTheDocument();
    });
    expect(screen.getByText("Run Weekly Revaluation")).toBeInTheDocument();
  });
});
