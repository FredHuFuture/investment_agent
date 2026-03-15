import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ToastContainer } from "../Toast";
import { ToastProvider, useToast } from "../../../contexts/ToastContext";

/**
 * Helper component that adds a toast on mount via the context.
 */
function ToastAdder({
  title,
  message,
  type = "success",
}: {
  title: string;
  message?: string;
  type?: "success" | "error" | "info" | "warning";
}) {
  const { addToast } = useToast();

  return (
    <button
      onClick={() => addToast({ type, title, message, duration: 0 })}
      data-testid="add-toast"
    >
      Add Toast
    </button>
  );
}

function renderWithProvider(ui: React.ReactElement) {
  return render(<ToastProvider>{ui}</ToastProvider>);
}

describe("ToastContainer", () => {
  it("renders nothing when no toasts exist", () => {
    const { container } = renderWithProvider(<ToastContainer />);
    expect(container.innerHTML).toBe("");
  });

  it("renders toast title text", async () => {
    renderWithProvider(
      <>
        <ToastAdder title="Operation succeeded" />
        <ToastContainer />
      </>,
    );

    await act(async () => {
      screen.getByTestId("add-toast").click();
    });

    expect(screen.getByText("Operation succeeded")).toBeInTheDocument();
  });

  it("renders toast message text", async () => {
    renderWithProvider(
      <>
        <ToastAdder title="Done" message="Your changes have been saved" />
        <ToastContainer />
      </>,
    );

    await act(async () => {
      screen.getByTestId("add-toast").click();
    });

    expect(
      screen.getByText("Your changes have been saved"),
    ).toBeInTheDocument();
  });

  it("close button exists with correct aria-label", async () => {
    renderWithProvider(
      <>
        <ToastAdder title="Info toast" />
        <ToastContainer />
      </>,
    );

    await act(async () => {
      screen.getByTestId("add-toast").click();
    });

    expect(
      screen.getByRole("button", { name: "Close notification" }),
    ).toBeInTheDocument();
  });
});
