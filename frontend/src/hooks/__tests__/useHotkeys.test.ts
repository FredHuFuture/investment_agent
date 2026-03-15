import { renderHook } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useHotkeys } from "../useHotkeys";

function fireKey(
  key: string,
  options: Partial<KeyboardEvent> = {},
  target?: HTMLElement,
) {
  const event = new KeyboardEvent("keydown", {
    key,
    bubbles: true,
    cancelable: true,
    ...options,
  });
  if (target) {
    Object.defineProperty(event, "target", { value: target });
  }
  document.dispatchEvent(event);
  return event;
}

describe("useHotkeys", () => {
  it("calls action when matching key combo is pressed", () => {
    const action = vi.fn();
    renderHook(() => useHotkeys({ k: action }));

    fireKey("k");

    expect(action).toHaveBeenCalledTimes(1);
  });

  it("prevents default on matching key", () => {
    const action = vi.fn();
    renderHook(() => useHotkeys({ k: action }));

    const event = fireKey("k");

    expect(event.defaultPrevented).toBe(true);
  });

  it("does not fire when target is an INPUT element", () => {
    const action = vi.fn();
    renderHook(() => useHotkeys({ "ctrl+k": action }));

    const input = document.createElement("input");
    const event = new KeyboardEvent("keydown", {
      key: "k",
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    Object.defineProperty(event, "target", { value: input, writable: false });
    document.dispatchEvent(event);

    expect(action).not.toHaveBeenCalled();
  });

  it("does not fire when target is a TEXTAREA element", () => {
    const action = vi.fn();
    renderHook(() => useHotkeys({ "ctrl+k": action }));

    const textarea = document.createElement("textarea");
    const event = new KeyboardEvent("keydown", {
      key: "k",
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    Object.defineProperty(event, "target", {
      value: textarea,
      writable: false,
    });
    document.dispatchEvent(event);

    expect(action).not.toHaveBeenCalled();
  });

  it("handles ctrl+key combo correctly", () => {
    const action = vi.fn();
    renderHook(() => useHotkeys({ "ctrl+k": action }));

    fireKey("k", { ctrlKey: true });

    expect(action).toHaveBeenCalledTimes(1);
  });

  it("cleans up event listener on unmount", () => {
    const action = vi.fn();
    const { unmount } = renderHook(() => useHotkeys({ k: action }));

    unmount();
    fireKey("k");

    expect(action).not.toHaveBeenCalled();
  });
});
