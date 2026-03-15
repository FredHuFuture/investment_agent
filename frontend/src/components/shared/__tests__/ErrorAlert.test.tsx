import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ErrorAlert from "../ErrorAlert";

describe("ErrorAlert", () => {
  it("renders error message text", () => {
    render(<ErrorAlert message="Something went wrong" />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("shows Retry button when onRetry is provided", async () => {
    const handleRetry = vi.fn();
    render(<ErrorAlert message="Network error" onRetry={handleRetry} />);
    const retryButton = screen.getByText("Retry");
    expect(retryButton).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(retryButton);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it("does not show Retry button when onRetry is not provided", () => {
    render(<ErrorAlert message="Fatal error" />);
    expect(screen.queryByText("Retry")).not.toBeInTheDocument();
  });
});
