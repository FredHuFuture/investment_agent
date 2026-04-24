// Snapshot tests lock Phase 4 visual contracts for CLOSE-04..06 UAT resolution.
// DO NOT run `vitest -u` in CI — regenerate snapshots locally only after intentional Phase 4 component changes.
/**
 * CLOSE-04: Snapshot test locking TargetWeightBar rendering contract
 * across all four states. If this snapshot changes, investigate whether
 * the UX-defined behavior (null/overweight/underweight/neutral) was
 * intentionally updated or whether a regression was introduced.
 *
 * Regenerate after intentional changes: `npx vitest -u`
 * Manual verification path: scripts/verify_close_04_target_weight.py
 */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import TargetWeightBar from "../TargetWeightBar";

describe("CLOSE-04: TargetWeightBar snapshot contract", () => {
  it("A: null target renders nothing", () => {
    const { container } = render(
      <TargetWeightBar actualWeight={0.1} targetWeight={null} ticker="AAPL" />,
    );
    expect(container).toMatchSnapshot();
  });

  it("B: overweight (+5pp) renders amber fill + '+5.0%' label", () => {
    const { container } = render(
      <TargetWeightBar actualWeight={0.15} targetWeight={0.10} ticker="AAPL" />,
    );
    expect(container).toMatchSnapshot();
  });

  it("C: underweight (-2pp) renders green fill + '-2.0%' label", () => {
    const { container } = render(
      <TargetWeightBar actualWeight={0.08} targetWeight={0.10} ticker="MSFT" />,
    );
    expect(container).toMatchSnapshot();
  });

  it("D: neutral (at target) renders '+0.0%' label", () => {
    const { container } = render(
      <TargetWeightBar actualWeight={0.10} targetWeight={0.10} ticker="NVDA" />,
    );
    expect(container).toMatchSnapshot();
  });
});
