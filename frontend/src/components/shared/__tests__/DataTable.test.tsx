import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DataTable, { type Column } from "../DataTable";

interface TestRow {
  id: number;
  name: string;
  value: number;
}

const testData: TestRow[] = [
  { id: 1, name: "Alpha", value: 30 },
  { id: 2, name: "Beta", value: 10 },
  { id: 3, name: "Gamma", value: 20 },
];

const columns: Column<TestRow>[] = [
  {
    key: "name",
    header: "Name",
    render: (r) => r.name,
    sortValue: (r) => r.name,
    searchValue: (r) => r.name,
  },
  {
    key: "value",
    header: "Value",
    render: (r) => String(r.value),
    sortValue: (r) => r.value,
    searchValue: (r) => String(r.value),
  },
];

describe("DataTable", () => {
  it("renders column headers and row data", () => {
    render(
      <DataTable columns={columns} data={testData} keyFn={(r) => r.id} />,
    );

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Value")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("Gamma")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
  });

  it("sort: click header toggles asc then desc then null", async () => {
    const user = userEvent.setup();
    render(
      <DataTable columns={columns} data={testData} keyFn={(r) => r.id} />,
    );

    const nameHeader = screen.getByText("Name");

    // Click once: asc sort (Alpha, Beta, Gamma)
    await user.click(nameHeader);
    const rows1 = screen.getAllByRole("row");
    // rows1[0] is header row, data rows start at [1]
    const cells1 = rows1.slice(1).map((row) => within(row).getAllByRole("cell")[0]?.textContent);
    expect(cells1).toEqual(["Alpha", "Beta", "Gamma"]);

    // Click again: desc sort (Gamma, Beta, Alpha)
    await user.click(nameHeader);
    const rows2 = screen.getAllByRole("row");
    const cells2 = rows2.slice(1).map((row) => within(row).getAllByRole("cell")[0]?.textContent);
    expect(cells2).toEqual(["Gamma", "Beta", "Alpha"]);

    // Click again: no sort (original order: Alpha, Beta, Gamma)
    await user.click(nameHeader);
    const rows3 = screen.getAllByRole("row");
    const cells3 = rows3.slice(1).map((row) => within(row).getAllByRole("cell")[0]?.textContent);
    expect(cells3).toEqual(["Alpha", "Beta", "Gamma"]);
  });

  it("shows emptyMessage when data is empty", () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
        keyFn={(r: TestRow) => r.id}
        emptyMessage="Nothing to display"
      />,
    );
    expect(screen.getByText("Nothing to display")).toBeInTheDocument();
  });

  it("onRowClick fires with correct row", async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={testData}
        keyFn={(r) => r.id}
        onRowClick={handleClick}
      />,
    );

    await user.click(screen.getByText("Beta"));
    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(handleClick).toHaveBeenCalledWith(testData[1]);
  });

  it("search filters rows when searchable is true", async () => {
    const user = userEvent.setup();
    render(
      <DataTable
        columns={columns}
        data={testData}
        keyFn={(r) => r.id}
        searchable
      />,
    );

    const searchInput = screen.getByPlaceholderText("Search...");
    await user.type(searchInput, "Alpha");

    // Wait for debounce to apply
    await vi.waitFor(() => {
      expect(screen.getByText("Alpha")).toBeInTheDocument();
      expect(screen.queryByText("Beta")).not.toBeInTheDocument();
      expect(screen.queryByText("Gamma")).not.toBeInTheDocument();
    });
  });

  it("shows emptyFilterMessage when search produces no results", async () => {
    const user = userEvent.setup();
    render(
      <DataTable
        columns={columns}
        data={testData}
        keyFn={(r) => r.id}
        searchable
        emptyFilterMessage="No matches found"
      />,
    );

    const searchInput = screen.getByPlaceholderText("Search...");
    await user.type(searchInput, "zzzzz");

    await vi.waitFor(() => {
      expect(screen.getByText("No matches found")).toBeInTheDocument();
    });
  });

  it("renders all rows when not paginated", () => {
    const manyRows: TestRow[] = Array.from({ length: 25 }, (_, i) => ({
      id: i + 1,
      name: `Item ${i + 1}`,
      value: i * 10,
    }));

    render(
      <DataTable columns={columns} data={manyRows} keyFn={(r) => r.id} />,
    );

    // All 25 rows should be rendered (not paginated by default)
    const dataRows = screen.getAllByRole("row").slice(1); // exclude header
    expect(dataRows.length).toBe(25);
  });
});
