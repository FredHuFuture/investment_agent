import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock endpoint functions used by NotificationPreferences, SystemInfoCard, and NotificationConfigCard
vi.mock("../../api/endpoints", () => ({
  testEmailNotification: vi.fn(),
  testTelegramNotification: vi.fn(),
  getSystemInfo: vi.fn().mockResolvedValue({
    data: { status: "ok", db_path: "test.db", version: "5.33", total_positions: 5, total_closed: 3, total_signals: 100, total_alerts: 50 },
    warnings: [],
  }),
  getNotificationConfig: vi.fn().mockResolvedValue({
    data: {
      smtp_host: "",
      smtp_port: 587,
      smtp_user: "",
      smtp_password: "",
      smtp_enabled: false,
      telegram_bot_token: "",
      telegram_chat_id: "",
      telegram_enabled: false,
      notify_critical: true,
      notify_high: true,
      notify_warning: false,
      notify_info: false,
    },
    warnings: [],
  }),
  saveNotificationConfig: vi.fn().mockResolvedValue({
    data: {
      smtp_host: "",
      smtp_port: 587,
      smtp_user: "",
      smtp_password: "",
      smtp_enabled: false,
      telegram_bot_token: "",
      telegram_chat_id: "",
      telegram_enabled: false,
      notify_critical: true,
      notify_high: true,
      notify_warning: false,
      notify_info: false,
    },
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

  it("renders Export Hub section with all download links", () => {
    renderPage();
    expect(screen.getByText("Export Hub")).toBeInTheDocument();
    // Original export links
    expect(screen.getByText("Portfolio CSV")).toBeInTheDocument();
    expect(screen.getByText("Trade Journal CSV")).toBeInTheDocument();
    expect(screen.getByText("Full Report")).toBeInTheDocument();
    expect(screen.getByText("All Signals CSV")).toBeInTheDocument();
    // New export links
    expect(screen.getByText("Alerts CSV")).toBeInTheDocument();
    expect(screen.getByText("Performance CSV")).toBeInTheDocument();
    expect(screen.getByText("Risk CSV")).toBeInTheDocument();
  });

  it("renders all 7 export buttons across 5 categories", () => {
    renderPage();
    const expectedLabels = [
      "Portfolio CSV",
      "Trade Journal CSV",
      "Full Report",
      "Performance CSV",
      "Risk CSV",
      "All Signals CSV",
      "Alerts CSV",
    ];
    for (const label of expectedLabels) {
      const link = screen.getByText(label);
      expect(link).toBeInTheDocument();
      expect(link.tagName).toBe("A");
      expect(link).toHaveAttribute("download");
    }
    // Verify all 5 category headings
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Performance")).toBeInTheDocument();
    expect(screen.getByText("Risk")).toBeInTheDocument();
    expect(screen.getByText("Signals")).toBeInTheDocument();
    expect(screen.getByText("Alerts")).toBeInTheDocument();
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

  it("renders Notification Configuration card", async () => {
    renderPage();
    expect(await screen.findByText("Notification Configuration")).toBeInTheDocument();
    expect(screen.getByText("Email (SMTP)")).toBeInTheDocument();
    expect(screen.getByText("Alert Severity Filters")).toBeInTheDocument();
    expect(screen.getByText("Save Configuration")).toBeInTheDocument();
  });
});
