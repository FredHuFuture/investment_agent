import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConfirmModal from "../ConfirmModal";

const defaultProps = {
  open: true,
  onClose: vi.fn(),
  onConfirm: vi.fn(),
  title: "Delete Item",
  description: "Are you sure you want to delete this?",
};

describe("ConfirmModal", () => {
  it("returns null when open is false", () => {
    const { container } = render(
      <ConfirmModal {...defaultProps} open={false} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders title and description when open", () => {
    render(<ConfirmModal {...defaultProps} />);
    expect(
      screen.getByRole("heading", { level: 2, name: "Delete Item" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Are you sure you want to delete this?"),
    ).toBeInTheDocument();
  });

  it("calls onConfirm on confirm button click", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<ConfirmModal {...defaultProps} onConfirm={onConfirm} />);
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("calls onClose on cancel button click", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ConfirmModal {...defaultProps} onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose on backdrop click", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = render(
      <ConfirmModal {...defaultProps} onClose={onClose} />,
    );
    // The backdrop is the div with bg-black/60
    const backdrop = container.querySelector(".bg-black\\/60")!;
    await user.click(backdrop);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows loading state when loading is true", () => {
    render(<ConfirmModal {...defaultProps} loading={true} />);
    const confirmButton = screen.getByRole("button", { name: /Confirm/i });
    expect(confirmButton).toBeDisabled();
  });

  it("has correct ARIA attributes for accessibility", () => {
    render(<ConfirmModal open={true} onClose={vi.fn()} onConfirm={vi.fn()} title="Test" description="desc" />);
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby", "confirm-modal-title");
    expect(dialog).toHaveAttribute("aria-describedby", "confirm-modal-desc");
  });
});
