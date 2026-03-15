import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock recharts to avoid canvas/SVG issues in jsdom
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "responsive-container" }, children),
  ComposedChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "composed-chart" }, children),
  AreaChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "area-chart" }, children),
  Area: () => null,
  Line: () => null,
  Scatter: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
  Bar: () => null,
  BarChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "bar-chart" }, children),
  CartesianGrid: () => null,
  Cell: () => null,
}));

// Mock ALL endpoint functions imported by BacktestPage and its children
vi.mock("../../api/endpoints", () => ({
  runBacktest: vi.fn(),
  runBatchBacktest: vi.fn(),
}));

import "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import BacktestPage from "../BacktestPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <BacktestPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("BacktestPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
  });

  it('renders "Backtest" heading', () => {
    renderPage();
    expect(screen.getByText("Backtest")).toBeInTheDocument();
  });

  it("renders backtest form with ticker input", () => {
    renderPage();
    expect(screen.getByText("Ticker")).toBeInTheDocument();
    const tickerInput = screen.getByDisplayValue("AAPL");
    expect(tickerInput).toBeInTheDocument();
  });

  it("renders mode toggle (Single / Batch)", () => {
    renderPage();
    expect(screen.getByText("single")).toBeInTheDocument();
    expect(screen.getByText("batch")).toBeInTheDocument();
  });

  it("renders Run Backtest submit button", () => {
    renderPage();
    expect(screen.getByText("Run Backtest")).toBeInTheDocument();
  });

  it("renders date inputs with default values", () => {
    renderPage();
    expect(screen.getByText("Start")).toBeInTheDocument();
    expect(screen.getByText("End")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2023-01-01")).toBeInTheDocument();
    expect(screen.getByDisplayValue("2025-12-31")).toBeInTheDocument();
  });

  it("renders signal threshold inputs", () => {
    renderPage();
    expect(screen.getByText("Buy Threshold")).toBeInTheDocument();
    expect(screen.getByText("Sell Threshold")).toBeInTheDocument();
  });
});
