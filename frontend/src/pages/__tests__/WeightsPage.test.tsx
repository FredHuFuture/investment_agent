import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import WeightsPage from "../WeightsPage";

/**
 * WeightsPage (Phase 06-02): rewritten as a thin <Navigate to="/calibration" replace />.
 * Tests verify the redirect is in place.
 */
describe("WeightsPage (redirect)", () => {
  // Test T10: renders a Navigate redirect to /calibration
  it("redirects /weights to /calibration", () => {
    // Render with a Routes setup so Navigate can actually change the path
    render(
      <MemoryRouter initialEntries={["/weights"]}>
        <Routes>
          <Route path="/weights" element={<WeightsPage />} />
          <Route path="/calibration" element={<div data-testid="calibration-landing">Calibration</div>} />
        </Routes>
      </MemoryRouter>,
    );
    // After redirect, the CalibrationPage landing marker should be visible
    expect(screen.getByTestId("calibration-landing")).toBeInTheDocument();
  });

  it("does not render the old donut page content", () => {
    render(
      <MemoryRouter initialEntries={["/weights"]}>
        <Routes>
          <Route path="/weights" element={<WeightsPage />} />
          <Route path="/calibration" element={<div>Calibration</div>} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.queryByText("Model Weights")).not.toBeInTheDocument();
    expect(screen.queryByText("Stock Agents")).not.toBeInTheDocument();
  });
});
