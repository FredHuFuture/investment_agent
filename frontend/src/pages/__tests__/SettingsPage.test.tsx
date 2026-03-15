import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock endpoint functions used by SettingsPage (called on button click only)
vi.mock("../../api/endpoints", () => ({
  testEmailNotification: vi.fn(),
  testTelegramNotification: vi.fn(),
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
  });

  it("renders Settings heading", () => {
    renderPage();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("renders Email Notifications section", () => {
    renderPage();
    expect(screen.getByText("Email Notifications")).toBeInTheDocument();
    expect(screen.getByText("Send Test Email")).toBeInTheDocument();
  });

  it("renders Telegram Notifications section", () => {
    renderPage();
    expect(screen.getByText("Telegram Notifications")).toBeInTheDocument();
    expect(screen.getByText("Send Test Telegram")).toBeInTheDocument();
  });

  it("renders Export section with download links", () => {
    renderPage();
    expect(screen.getByText("Export")).toBeInTheDocument();
    expect(screen.getByText("Portfolio CSV")).toBeInTheDocument();
    expect(screen.getByText("Trade Journal CSV")).toBeInTheDocument();
    expect(screen.getByText("Full Report")).toBeInTheDocument();
    expect(screen.getByText("All Signals CSV")).toBeInTheDocument();
  });

  it("renders configuration guidance sections", () => {
    renderPage();
    const configSections = screen.getAllByText("Configuration");
    expect(configSections.length).toBe(2);
  });
});
