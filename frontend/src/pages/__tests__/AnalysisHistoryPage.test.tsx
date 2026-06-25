import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../api/endpoints", () => ({
  getAnalysisHistory: vi.fn(),
  getAnalyzedTickers: vi.fn(),
}));

import { getAnalysisHistory, getAnalyzedTickers } from "../../api/endpoints";
import { invalidateCache } from "../../lib/cache";
import AnalysisHistoryPage from "../AnalysisHistoryPage";

const mockGetAnalysisHistory = vi.mocked(getAnalysisHistory);
const mockGetAnalyzedTickers = vi.mocked(getAnalyzedTickers);

// final_confidence and agent confidence are stored on a 0-100 scale.
const entry = {
  id: 1,
  ticker: "AAPL",
  asset_type: "stock",
  final_signal: "BUY",
  final_confidence: 72,
  regime: "RISK_ON",
  raw_score: 0.4,
  consensus_score: 0.8,
  agent_signals: [
    { agent_name: "TechnicalAgent", signal: "BUY", confidence: 85 },
  ],
  reasoning: "Momentum strong",
  created_at: "2024-06-15 10:00:00",
};

function renderPage() {
  return render(
    <MemoryRouter>
      <AnalysisHistoryPage />
    </MemoryRouter>,
  );
}

describe("AnalysisHistoryPage confidence display", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    invalidateCache();
    mockGetAnalyzedTickers.mockResolvedValue({ data: ["AAPL"], warnings: [] });
    mockGetAnalysisHistory.mockResolvedValue({ data: [entry], warnings: [] });
  });

  it("renders final_confidence as-is (0-100), not multiplied by 100", async () => {
    renderPage();
    expect(await screen.findByText("72%")).toBeInTheDocument();
    expect(screen.queryByText("7200%")).not.toBeInTheDocument();
  });

  it("renders agent confidence as-is when a row is expanded", async () => {
    renderPage();
    const row = await screen.findByRole("button", { name: /AAPL/ });
    fireEvent.click(row);
    await waitFor(() =>
      expect(screen.getByText("TechnicalAgent")).toBeInTheDocument(),
    );
    expect(screen.getByText("85%")).toBeInTheDocument();
    expect(screen.queryByText("8500%")).not.toBeInTheDocument();
  });
});
