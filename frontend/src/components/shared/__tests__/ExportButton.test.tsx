import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "../../../contexts/ToastContext";
import ExportButton from "../ExportButton";

// ------------------------------------------------------------------
// Mocks
// ------------------------------------------------------------------

const mockToastError = vi.fn();

vi.mock("../../../contexts/ToastContext", async () => {
  const actual = await vi.importActual<typeof import("../../../contexts/ToastContext")>(
    "../../../contexts/ToastContext",
  );
  return {
    ...actual,
    useToast: () => ({
      toasts: [],
      addToast: vi.fn(),
      removeToast: vi.fn(),
      toast: {
        success: vi.fn(),
        error: mockToastError,
        info: vi.fn(),
        warning: vi.fn(),
      },
    }),
  };
});

beforeEach(() => {
  vi.restoreAllMocks();
  mockToastError.mockClear();
});

// Helper to wrap component with providers
function renderWithProviders(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

// ------------------------------------------------------------------
// Tests
// ------------------------------------------------------------------

describe("ExportButton", () => {
  it("renders with provided label text", () => {
    renderWithProviders(
      <ExportButton
        endpoint="/api/export/portfolio/csv"
        filename="portfolio.csv"
        label="Download CSV"
      />,
    );
    expect(screen.getByText("Download CSV")).toBeInTheDocument();
  });

  it('uses default label "Export" when no label prop is provided', () => {
    renderWithProviders(
      <ExportButton
        endpoint="/api/export/portfolio/csv"
        filename="portfolio.csv"
      />,
    );
    expect(screen.getByText("Export")).toBeInTheDocument();
  });

  it("shows loading state when button is clicked", async () => {
    // fetch that never resolves so we can observe loading state
    const neverResolve = new Promise<Response>(() => {});
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(neverResolve));

    renderWithProviders(
      <ExportButton
        endpoint="/api/export/portfolio/csv"
        filename="portfolio.csv"
        label="Export"
      />,
    );

    const user = userEvent.setup();
    const button = screen.getByRole("button");

    await user.click(button);

    // Button should be disabled / aria-busy while loading
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("triggers file download on successful fetch", async () => {
    const blob = new Blob(["csv,content"], { type: "text/csv" });
    const fakeResponse = {
      ok: true,
      blob: () => Promise.resolve(blob),
    } as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse));

    // Mock URL.createObjectURL / revokeObjectURL
    const fakeUrl = "blob:http://localhost/fake";
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn().mockReturnValue(fakeUrl),
      revokeObjectURL: vi.fn(),
    });

    renderWithProviders(
      <ExportButton
        endpoint="/api/export/portfolio/csv"
        filename="portfolio.csv"
        label="Download"
      />,
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/api/export/portfolio/csv");
    });
  });

  it("shows error toast on fetch failure", async () => {
    const fakeResponse = {
      ok: false,
      status: 500,
    } as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse));

    renderWithProviders(
      <ExportButton
        endpoint="/api/export/portfolio/csv"
        filename="portfolio.csv"
      />,
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole("button"));

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith(
        "Export error",
        "Export failed (500)",
      );
    });
  });
});
