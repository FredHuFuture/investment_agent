import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock endpoint functions used by NotificationPreferences and SystemInfoCard
vi.mock("../../api/endpoints", () => ({
  testEmailNotification: vi.fn(),
  testTelegramNotification: vi.fn(),
  getSystemInfo: vi.fn().mockResolvedValue({
    data: { status: "ok", db_path: "test.db", version: "5.33", total_positions: 5, total_closed: 3, total_signals: 100, total_alerts: 50 },
    warnings: [],
  }),
}));

import { invalidateCache } from "../../lib/cache";
import SettingsPage from "../SettingsPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <SettingsPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
    localStorage.clear();
  });

  it("renders Settings heading", () => {
    renderPage();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders Appearance section with theme toggle buttons", () => {
    renderPage();
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Dark")).toBeInTheDocument();
    expect(screen.getByText("Light")).toBeInTheDocument();
    expect(screen.getByText("System")).toBeInTheDocument();
  });

  it("renders Notifications section with test buttons", () => {
    renderPage();
    expect(screen.getByText("Notifications")).toBeInTheDocument();
    expect(screen.getByText("Send Test Email")).toBeInTheDocument();
    expect(screen.getByText("Send Test Telegram")).toBeInTheDocument();
  });

  it("renders Data & Cache section", () => {
    renderPage();
    expect(screen.getByText("Data & Cache")).toBeInTheDocument();
    expect(screen.getByText("Clear Cache")).toBeInTheDocument();
  });

  it("renders Export section with download links", () => {
    renderPage();
    expect(screen.getByText("Export")).toBeInTheDocument();
    expect(screen.getByText("Portfolio CSV")).toBeInTheDocument();
    expect(screen.getByText("Trade Journal CSV")).toBeInTheDocument();
    expect(screen.getByText("Full Report")).toBeInTheDocument();
    expect(screen.getByText("All Signals CSV")).toBeInTheDocument();
  });

  it("renders configuration guidance section", () => {
    renderPage();
    expect(screen.getByText("Configuration")).toBeInTheDocument();
  });

  it("renders cache TTL options", () => {
    renderPage();
    expect(screen.getByText("15s")).toBeInTheDocument();
    expect(screen.getByText("30s")).toBeInTheDocument();
    expect(screen.getByText("60s")).toBeInTheDocument();
    expect(screen.getByText("2min")).toBeInTheDocument();
    expect(screen.getByText("5min")).toBeInTheDocument();
  });

  it("renders notification toggle labels", () => {
    renderPage();
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("Telegram")).toBeInTheDocument();
  });
});
