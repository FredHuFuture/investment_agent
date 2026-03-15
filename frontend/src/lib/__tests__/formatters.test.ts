import { describe, it, expect } from "vitest";
import { formatCurrency, formatPct, formatDate, formatNumber, formatRelativeTime, formatRelativeDate, pnlColor, holdColor } from "../formatters";

describe("formatCurrency", () => {
  it("formats a positive integer", () => {
    expect(formatCurrency(1234)).toBe("$1,234");
  });

  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("$0");
  });

  it("formats a negative number", () => {
    const result = formatCurrency(-500);
    // Locale may use hyphen-minus or minus sign
    expect(result).toMatch(/^-?\$500$/);
  });

  it("rounds decimal amounts to whole dollars", () => {
    expect(formatCurrency(99.99)).toBe("$100");
  });

  it("formats large numbers with commas", () => {
    expect(formatCurrency(1_000_000)).toBe("$1,000,000");
  });
});

describe("formatPct", () => {
  it("formats a positive value with + sign", () => {
    expect(formatPct(12.34)).toBe("+12.3%");
  });

  it("formats zero without + sign", () => {
    expect(formatPct(0)).toBe("0.0%");
  });

  it("formats a negative value with - sign", () => {
    expect(formatPct(-5.67)).toBe("-5.7%");
  });

  it("respects custom decimal places", () => {
    expect(formatPct(3.456, 2)).toBe("+3.46%");
  });

  it("uses default 1 decimal place", () => {
    expect(formatPct(1.999)).toBe("+2.0%");
  });
});

describe("formatDate", () => {
  it("formats ISO date string", () => {
    const result = formatDate("2024-06-15T10:30:00Z");
    expect(result).toContain("Jun");
    expect(result).toContain("15");
    expect(result).toContain("2024");
  });

  it("handles backend space-separated format", () => {
    const result = formatDate("2024-03-01 14:00:00");
    expect(result).toContain("Mar");
    expect(result).toContain("1");
    expect(result).toContain("2024");
  });

  it("returns original string for invalid dates", () => {
    expect(formatDate("not-a-date")).toBe("not-a-date");
  });

  it("handles date-only ISO strings", () => {
    const result = formatDate("2023-12-25");
    expect(result).toContain("Dec");
    expect(result).toContain("2023");
  });
});

describe("formatNumber", () => {
  it("formats with default 2 decimal places", () => {
    expect(formatNumber(1234.5)).toBe("1,234.50");
  });

  it("formats zero", () => {
    expect(formatNumber(0)).toBe("0.00");
  });

  it("formats with custom decimal places", () => {
    expect(formatNumber(3.14159, 4)).toBe("3.1416");
  });

  it("formats a negative number", () => {
    const result = formatNumber(-42.1, 1);
    expect(result).toMatch(/^-?42\.1$/);
  });

  it("formats large numbers with commas", () => {
    expect(formatNumber(1_234_567.89)).toBe("1,234,567.89");
  });
});

describe("formatRelativeTime", () => {
  it("returns empty string for null", () => {
    expect(formatRelativeTime(null)).toBe("");
  });
  it("returns 'just now' for recent timestamp", () => {
    expect(formatRelativeTime(Date.now() - 5000)).toBe("just now");
  });
  it("returns minutes ago", () => {
    expect(formatRelativeTime(Date.now() - 300000)).toBe("5m ago");
  });
  it("returns hours ago", () => {
    expect(formatRelativeTime(Date.now() - 7200000)).toBe("2h ago");
  });
});

describe("formatRelativeDate", () => {
  it("returns empty string for empty input", () => {
    expect(formatRelativeDate("")).toBe("");
  });
  it("returns minutes ago for recent date", () => {
    const fiveMinAgo = new Date(Date.now() - 300000).toISOString();
    expect(formatRelativeDate(fiveMinAgo)).toBe("5m ago");
  });
  it("returns hours ago", () => {
    const twoHoursAgo = new Date(Date.now() - 7200000).toISOString();
    expect(formatRelativeDate(twoHoursAgo)).toBe("2h ago");
  });
  it("returns days ago", () => {
    const threeDaysAgo = new Date(Date.now() - 259200000).toISOString();
    expect(formatRelativeDate(threeDaysAgo)).toBe("3d ago");
  });
});

describe("pnlColor", () => {
  it("returns emerald for positive", () => {
    expect(pnlColor(5)).toBe("text-emerald-400");
  });
  it("returns red for negative", () => {
    expect(pnlColor(-3)).toBe("text-red-400");
  });
  it("returns gray for zero", () => {
    expect(pnlColor(0)).toBe("text-gray-400");
  });
});

describe("holdColor", () => {
  it("returns gray when expected is null", () => {
    expect(holdColor(10, null)).toBe("text-gray-400");
  });
  it("returns red when overdue", () => {
    expect(holdColor(100, 50)).toBe("text-red-400");
  });
  it("returns yellow when nearing deadline", () => {
    expect(holdColor(85, 100)).toBe("text-yellow-400");
  });
  it("returns emerald when on track", () => {
    expect(holdColor(30, 100)).toBe("text-emerald-400");
  });
});
