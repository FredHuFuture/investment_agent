import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";
import { ToastProvider } from "../../contexts/ToastContext";
import type { BacktestResult } from "../../api/types";

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
  LineChart: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { "data-testid": "line-chart" }, children),
}));

// Mock ALL endpoint functions imported by BacktestPage and its children
vi.mock("../../api/endpoints", () => ({
  runBacktest: vi.fn(),
  runBatchBacktest: vi.fn(),
}));

import "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import BacktestPage from "../BacktestPage";
import BacktestResults from "../../components/backtest/BacktestResults";
import BacktestComparison from "../../components/backtest/BacktestComparison";
import type { SavedBacktestRun } from "../../lib/backtestStorage";

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <BacktestPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

/** Mock backtest result with all 14 metrics. */
const fullMockResult: BacktestResult = {
  metrics: {
    total_return_pct: 25.3,
    annualized_return_pct: 12.1,
    max_drawdown_pct: -8.5,
    sharpe_ratio: 1.45,
    win_rate: 62.5,
    total_trades: 48,
    sortino_ratio: 2.10,
    calmar_ratio: 1.42,
    profit_factor: 1.85,
    avg_win_pct: 3.2,
    avg_loss_pct: -1.8,
    avg_holding_days: 14.7,
    max_consecutive_wins: 7,
    max_consecutive_losses: 3,
  },
  trades: [],
  trades_count: 48,
  equity_curve: [{ date: "2023-01-01", equity: 100000 }],
  signals_log: [],
};

function renderResults(data: BacktestResult = fullMockResult) {
  return render(<BacktestResults data={data} />);
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

describe("BacktestResults - Advanced Metrics", () => {
  it('renders the "Show Advanced Metrics" toggle button', () => {
    renderResults();
    expect(screen.getByText("Show Advanced Metrics")).toBeInTheDocument();
  });

  it("does not show advanced metrics panel by default", () => {
    renderResults();
    expect(screen.queryByTestId("advanced-metrics-panel")).not.toBeInTheDocument();
  });

  it("shows advanced metrics panel when toggle is clicked", () => {
    renderResults();
    const toggleBtn = screen.getByTestId("toggle-advanced-metrics");
    fireEvent.click(toggleBtn);
    expect(screen.getByTestId("advanced-metrics-panel")).toBeInTheDocument();
    expect(screen.getByText("Hide Advanced Metrics")).toBeInTheDocument();
  });

  it("displays sortino_ratio in the expanded section", () => {
    renderResults();
    fireEvent.click(screen.getByTestId("toggle-advanced-metrics"));
    expect(screen.getByText("Sortino Ratio")).toBeInTheDocument();
    expect(screen.getByText("2.10")).toBeInTheDocument();
  });

  it("displays profit_factor in the expanded section", () => {
    renderResults();
    fireEvent.click(screen.getByTestId("toggle-advanced-metrics"));
    expect(screen.getByText("Profit Factor")).toBeInTheDocument();
    expect(screen.getByText("1.85")).toBeInTheDocument();
  });

  it("displays all 8 advanced metrics when all are defined", () => {
    renderResults();
    fireEvent.click(screen.getByTestId("toggle-advanced-metrics"));
    expect(screen.getByText("Sortino Ratio")).toBeInTheDocument();
    expect(screen.getByText("Calmar Ratio")).toBeInTheDocument();
    expect(screen.getByText("Profit Factor")).toBeInTheDocument();
    expect(screen.getByText("Avg Win")).toBeInTheDocument();
    expect(screen.getByText("Avg Loss")).toBeInTheDocument();
    expect(screen.getByText("Avg Holding Days")).toBeInTheDocument();
    expect(screen.getByText("Max Consecutive Wins")).toBeInTheDocument();
    expect(screen.getByText("Max Consecutive Losses")).toBeInTheDocument();
  });

  it("hides the toggle when no advanced metrics are defined", () => {
    const minimalResult: BacktestResult = {
      metrics: {
        total_return_pct: 10,
        annualized_return_pct: 5,
        max_drawdown_pct: -3,
        sharpe_ratio: 1.0,
        win_rate: 50,
        total_trades: 20,
      },
      trades: [],
      trades_count: 20,
      equity_curve: [{ date: "2023-01-01", equity: 100000 }],
      signals_log: [],
    };
    renderResults(minimalResult);
    expect(screen.queryByTestId("toggle-advanced-metrics")).not.toBeInTheDocument();
  });

  it("hides advanced metrics again when toggle is clicked twice", () => {
    renderResults();
    const toggleBtn = screen.getByTestId("toggle-advanced-metrics");
    fireEvent.click(toggleBtn);
    expect(screen.getByTestId("advanced-metrics-panel")).toBeInTheDocument();
    fireEvent.click(toggleBtn);
    expect(screen.queryByTestId("advanced-metrics-panel")).not.toBeInTheDocument();
    expect(screen.getByText("Show Advanced Metrics")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// BacktestComparison
// ---------------------------------------------------------------------------

/** Helper to create mock saved backtest runs. */
function makeSavedRun(overrides: Partial<SavedBacktestRun> & { id: string }): SavedBacktestRun {
  return {
    ticker: "AAPL",
    label: "Run " + overrides.id,
    params: { start_date: "2023-01-01", end_date: "2024-01-01" },
    metrics: {
      total_return_pct: 15.0,
      annualized_return_pct: 10.0,
      max_drawdown_pct: -5.0,
      sharpe_ratio: 1.2,
      win_rate: 55.0,
      total_trades: 30,
      sortino_ratio: 1.8,
      profit_factor: 1.5,
    },
    equity_curve: [
      { date: "2023-01-01", equity: 100000 },
      { date: "2023-06-01", equity: 110000 },
      { date: "2024-01-01", equity: 115000 },
    ],
    saved_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("BacktestComparison", () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "Compare Backtests" heading with 2 saved runs', () => {
    const runs = [
      makeSavedRun({ id: "run1", label: "AAPL Bull", ticker: "AAPL", metrics: { ...fullMockResult.metrics, total_return_pct: 25.3 } }),
      makeSavedRun({ id: "run2", label: "MSFT Bear", ticker: "MSFT", metrics: { ...fullMockResult.metrics, total_return_pct: 10.0 } }),
    ];

    render(<BacktestComparison runs={runs} onClose={mockOnClose} />);

    expect(screen.getByText("Compare Backtests")).toBeInTheDocument();
    expect(screen.getByTestId("backtest-comparison")).toBeInTheDocument();
  });

  it("renders Run A and Run B dropdown selects", () => {
    const runs = [
      makeSavedRun({ id: "run1", label: "Run Alpha" }),
      makeSavedRun({ id: "run2", label: "Run Beta" }),
    ];

    render(<BacktestComparison runs={runs} onClose={mockOnClose} />);

    expect(screen.getByTestId("select-run-a")).toBeInTheDocument();
    expect(screen.getByTestId("select-run-b")).toBeInTheDocument();
  });

  it("renders metrics comparison table with Diff column", () => {
    const runs = [
      makeSavedRun({ id: "run1" }),
      makeSavedRun({ id: "run2" }),
    ];

    render(<BacktestComparison runs={runs} onClose={mockOnClose} />);

    const table = screen.getByTestId("comparison-metrics-table");
    expect(table).toBeInTheDocument();
    expect(screen.getByText("Metric")).toBeInTheDocument();
    expect(screen.getByText("Diff")).toBeInTheDocument();
    expect(screen.getByText("Total Return")).toBeInTheDocument();
    expect(screen.getByText("Sharpe Ratio")).toBeInTheDocument();
    // "Run A" and "Run B" appear as both labels and table headers
    expect(screen.getAllByText("Run A").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Run B").length).toBeGreaterThanOrEqual(1);
  });

  it("renders summary verdict", () => {
    const runs = [
      makeSavedRun({ id: "run1", metrics: { ...fullMockResult.metrics, total_return_pct: 10.0 } }),
      makeSavedRun({ id: "run2", metrics: { ...fullMockResult.metrics, total_return_pct: 20.0 } }),
    ];

    render(<BacktestComparison runs={runs} onClose={mockOnClose} />);

    expect(screen.getByTestId("comparison-verdict")).toBeInTheDocument();
    expect(screen.getByTestId("comparison-verdict").textContent).toContain("Run B outperforms Run A");
  });

  it("shows empty state when fewer than 2 runs are provided", () => {
    const runs = [makeSavedRun({ id: "run1" })];

    render(<BacktestComparison runs={runs} onClose={mockOnClose} />);

    expect(screen.getByText("Compare Backtests")).toBeInTheDocument();
    expect(screen.getByText("Select at least 2 saved runs to compare.")).toBeInTheDocument();
  });

  it("calls onClose when Close button is clicked", () => {
    const runs = [
      makeSavedRun({ id: "run1" }),
      makeSavedRun({ id: "run2" }),
    ];

    render(<BacktestComparison runs={runs} onClose={mockOnClose} />);

    fireEvent.click(screen.getByText("Close"));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });
});
