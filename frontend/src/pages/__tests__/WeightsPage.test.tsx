import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../../contexts/ToastContext";

// Mock ALL endpoint functions imported by WeightsPage
vi.mock("../../api/endpoints", () => ({
  getWeights: vi.fn(),
}));

import { getWeights } from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import WeightsPage from "../WeightsPage";

const mockGetWeights = vi.mocked(getWeights);

const mockWeightsData = {
  weights: {
    stock: { TechnicalAgent: 0.3, FundamentalAgent: 0.45, MacroAgent: 0.25 },
    btc: { CryptoAgent: 1.0 },
  },
  crypto_factor_weights: {
    market_structure: 0.15,
    momentum_trend: 0.2,
    volatility_risk: 0.15,
  },
  buy_threshold: 0.3,
  sell_threshold: -0.3,
  source: "default",
  sample_size: 0,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <WeightsPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("WeightsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
  });

  it("renders skeleton components while loading", () => {
    mockGetWeights.mockReturnValue(new Promise(() => {}));
    renderPage();
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error alert when API rejects", async () => {
    mockGetWeights.mockRejectedValue(new Error("Server unavailable"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Server unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it('renders "Model Weights" heading when data loads', async () => {
    mockGetWeights.mockResolvedValue({
      data: mockWeightsData as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Model Weights")).toBeInTheDocument();
    });
  });

  it("renders stock agent weights", async () => {
    mockGetWeights.mockResolvedValue({
      data: mockWeightsData as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Stock Agents")).toBeInTheDocument();
    });
    expect(screen.getByText("Fundamental")).toBeInTheDocument();
    expect(screen.getByText("Technical")).toBeInTheDocument();
    expect(screen.getByText("Macro")).toBeInTheDocument();
  });

  it("renders buy and sell threshold pills", async () => {
    mockGetWeights.mockResolvedValue({
      data: mockWeightsData as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Buy Threshold")).toBeInTheDocument();
    });
    expect(screen.getByText("Sell Threshold")).toBeInTheDocument();
    expect(screen.getByText("0.30")).toBeInTheDocument();
    expect(screen.getByText("-0.30")).toBeInTheDocument();
  });

  it("renders crypto factor weights section", async () => {
    mockGetWeights.mockResolvedValue({
      data: mockWeightsData as never,
      warnings: [],
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Crypto Factors")).toBeInTheDocument();
    });
    expect(screen.getByText("Market Structure")).toBeInTheDocument();
    expect(screen.getByText("Momentum Trend")).toBeInTheDocument();
    expect(screen.getByText("Volatility Risk")).toBeInTheDocument();
  });
});
