import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TextInput, SelectInput } from "../Input";

describe("TextInput", () => {
  it("renders with label and associates htmlFor", () => {
    render(<TextInput label="Username" />);
    const label = screen.getByText("Username");
    expect(label).toBeInTheDocument();
    expect(label).toHaveAttribute("for", "username");
    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("id", "username");
  });

  it("displays error message", () => {
    render(<TextInput label="Email" error="Invalid email" />);
    expect(screen.getByText("Invalid email")).toBeInTheDocument();
  });

  it("shows hint when no error", () => {
    render(<TextInput label="Name" hint="Enter your full name" />);
    expect(screen.getByText("Enter your full name")).toBeInTheDocument();
  });

  it("hides hint when error is present", () => {
    render(
      <TextInput label="Name" hint="Enter your full name" error="Required" />,
    );
    expect(screen.getByText("Required")).toBeInTheDocument();
    expect(screen.queryByText("Enter your full name")).not.toBeInTheDocument();
  });

  it("fires onChange handler", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    render(<TextInput label="Field" onChange={handleChange} />);
    const input = screen.getByRole("textbox");
    await user.type(input, "a");
    expect(handleChange).toHaveBeenCalled();
  });

  it("supports disabled state", () => {
    render(<TextInput label="Disabled" disabled />);
    expect(screen.getByRole("textbox")).toBeDisabled();
  });
});

describe("SelectInput", () => {
  const options = [
    { value: "a", label: "Option A" },
    { value: "b", label: "Option B" },
    { value: "c", label: "Option C" },
  ];

  it("renders all options", () => {
    render(<SelectInput options={options} />);
    const selectOptions = screen.getAllByRole("option");
    expect(selectOptions).toHaveLength(3);
    expect(selectOptions[0]).toHaveTextContent("Option A");
    expect(selectOptions[1]).toHaveTextContent("Option B");
    expect(selectOptions[2]).toHaveTextContent("Option C");
  });

  it("displays error state", () => {
    render(<SelectInput options={options} error="Selection required" />);
    expect(screen.getByText("Selection required")).toBeInTheDocument();
  });

  it("renders label with htmlFor", () => {
    render(<SelectInput label="Category" options={options} />);
    const label = screen.getByText("Category");
    expect(label).toHaveAttribute("for", "category");
    const select = screen.getByRole("combobox");
    expect(select).toHaveAttribute("id", "category");
  });
});
