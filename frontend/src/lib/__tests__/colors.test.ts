import { describe, it, expect } from "vitest";
import { signalColor, signalBg, severityColor, severityBg } from "../colors";

describe("signalColor", () => {
  it("maps BUY to green", () => {
    expect(signalColor.BUY).toBe("text-green-400");
  });

  it("maps SELL to red", () => {
    expect(signalColor.SELL).toBe("text-red-400");
  });

  it("maps HOLD to yellow", () => {
    expect(signalColor.HOLD).toBe("text-yellow-400");
  });

  it("returns undefined for unknown signal", () => {
    expect(signalColor["UNKNOWN"]).toBeUndefined();
  });
});

describe("signalBg", () => {
  it("maps BUY to green bg with text", () => {
    expect(signalBg.BUY).toBe("bg-green-400/20 text-green-400");
  });

  it("maps SELL to red bg with text", () => {
    expect(signalBg.SELL).toBe("bg-red-400/20 text-red-400");
  });

  it("maps HOLD to yellow bg with text", () => {
    expect(signalBg.HOLD).toBe("bg-yellow-400/20 text-yellow-400");
  });

  it("returns undefined for unknown signal", () => {
    expect(signalBg["UNKNOWN"]).toBeUndefined();
  });
});

describe("severityColor", () => {
  it("maps CRITICAL to red", () => {
    expect(severityColor.CRITICAL).toBe("text-red-400");
  });

  it("maps HIGH to orange", () => {
    expect(severityColor.HIGH).toBe("text-orange-400");
  });

  it("maps WARNING to yellow", () => {
    expect(severityColor.WARNING).toBe("text-yellow-400");
  });

  it("maps INFO to blue", () => {
    expect(severityColor.INFO).toBe("text-blue-400");
  });

  it("returns undefined for unknown severity", () => {
    expect(severityColor["NONE"]).toBeUndefined();
  });
});

describe("severityBg", () => {
  it("maps CRITICAL to red bg with text", () => {
    expect(severityBg.CRITICAL).toBe("bg-red-400/20 text-red-400");
  });

  it("maps HIGH to orange bg with text", () => {
    expect(severityBg.HIGH).toBe("bg-orange-400/20 text-orange-400");
  });

  it("maps WARNING to yellow bg with text", () => {
    expect(severityBg.WARNING).toBe("bg-yellow-400/20 text-yellow-400");
  });

  it("maps INFO to blue bg with text", () => {
    expect(severityBg.INFO).toBe("bg-blue-400/20 text-blue-400");
  });

  it("returns undefined for unknown severity", () => {
    expect(severityBg["NONE"]).toBeUndefined();
  });
});
