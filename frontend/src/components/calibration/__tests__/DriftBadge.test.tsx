import { render } from "@testing-library/react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import DriftBadge from "../DriftBadge";
import type { DriftLogEntry } from "../../../api/types";

const FROZEN_NOW = Date.parse("2026-04-26T22:30:00.000Z");

function makeEntry(overrides: Partial<DriftLogEntry>): DriftLogEntry {
  return {
    agent_name: "TechnicalAgent",
    asset_type: "stock",
    evaluated_at: "2026-04-26T17:30:00.000Z", // 5h before FROZEN_NOW
    current_icir: 0.42,
    avg_icir_60d: 0.55,
    delta_pct: -23.6,
    threshold_type: "pct_drop",
    triggered: false,
    preliminary_threshold: false,
    weight_before: 0.25,
    weight_after: 0.21,
    ...overrides,
  };
}

describe("DriftBadge", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(FROZEN_NOW);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when entry is null", () => {
    const { container } = render(<DriftBadge entry={null} agentName="X" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders amber Preliminary state", () => {
    const entry = makeEntry({ preliminary_threshold: true, triggered: false });
    const { getByTestId } = render(
      <DriftBadge entry={entry} agentName="MacroAgent" />,
    );
    const badge = getByTestId("cal-drift-badge-MacroAgent");
    expect(badge.textContent).toMatch(/Preliminary/i);
    expect(badge.className).toMatch(/amber/);
  });

  it("renders red Drift Detected state with delta_pct when triggered + recent", () => {
    const entry = makeEntry({ triggered: true, preliminary_threshold: false });
    const { getByTestId } = render(
      <DriftBadge entry={entry} agentName="TechnicalAgent" />,
    );
    const badge = getByTestId("cal-drift-badge-TechnicalAgent");
    expect(badge.textContent).toMatch(/Drift Detected/i);
    expect(badge.textContent).toMatch(/-23\.6%/);
    expect(badge.className).toMatch(/red/);
  });

  it("renders nothing when triggered but evaluated_at > 7 days ago", () => {
    const eightDaysAgo = new Date(
      FROZEN_NOW - 8 * 24 * 60 * 60 * 1000,
    ).toISOString();
    const entry = makeEntry({
      triggered: true,
      preliminary_threshold: false,
      evaluated_at: eightDaysAgo,
    });
    const { container } = render(
      <DriftBadge entry={entry} agentName="StaleAgent" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing in OK state (triggered=false, preliminary=false)", () => {
    const entry = makeEntry({ triggered: false, preliminary_threshold: false });
    const { container } = render(
      <DriftBadge entry={entry} agentName="HappyAgent" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("uses absolute_floor tooltip when threshold_type=absolute_floor", () => {
    const entry = makeEntry({
      triggered: true,
      preliminary_threshold: false,
      threshold_type: "absolute_floor",
    });
    const { getByTestId } = render(
      <DriftBadge entry={entry} agentName="FloorAgent" />,
    );
    const badge = getByTestId("cal-drift-badge-FloorAgent");
    expect(badge.title).toMatch(/floor.*0\.5.*2 consecutive/i);
  });

  it("snapshot: preliminary state", () => {
    const entry = makeEntry({ preliminary_threshold: true, triggered: false });
    const { container } = render(
      <DriftBadge entry={entry} agentName="SnapAgent" />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("snapshot: triggered state", () => {
    const entry = makeEntry({ triggered: true, preliminary_threshold: false });
    const { container } = render(
      <DriftBadge entry={entry} agentName="SnapAgent" />,
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it("snapshot: null state", () => {
    const { container } = render(<DriftBadge entry={null} agentName="SnapAgent" />);
    expect(container.firstChild).toMatchSnapshot();
  });
});
