import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Card, CardHeader, CardBody } from "../Card";

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("applies padding variants", () => {
    const { rerender } = render(<Card padding="none">content</Card>);
    const getCard = () => screen.getByText("content").closest("div")!;

    expect(getCard().className).toContain("p-0");

    rerender(<Card padding="sm">content</Card>);
    expect(getCard().className).toContain("p-3");

    rerender(<Card padding="md">content</Card>);
    expect(getCard().className).toContain("p-5");

    rerender(<Card padding="lg">content</Card>);
    expect(getCard().className).toContain("p-6");
  });
});

describe("CardHeader", () => {
  it("renders title", () => {
    render(<CardHeader title="My Title" />);
    expect(
      screen.getByRole("heading", { level: 3, name: "My Title" }),
    ).toBeInTheDocument();
  });

  it("renders subtitle and action slot", () => {
    render(
      <CardHeader
        title="Title"
        subtitle="Subtitle text"
        action={<button>Action</button>}
      />,
    );
    expect(screen.getByText("Subtitle text")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Action" }),
    ).toBeInTheDocument();
  });
});

describe("CardBody", () => {
  it("renders children", () => {
    render(<CardBody>Body content</CardBody>);
    expect(screen.getByText("Body content")).toBeInTheDocument();
  });
});
