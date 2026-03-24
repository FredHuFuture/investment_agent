import { useState, useMemo, useCallback, type ReactNode } from "react";
import Pagination from "./Pagination";
import TableSearch from "./TableSearch";

// ---------------------------------------------------------------------------
// Column definition (backward-compatible -- `key` preserved from original)
// ---------------------------------------------------------------------------
export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => number | string;
  /** Text value used for search filtering. Falls back to render text content. */
  searchValue?: (row: T) => string;
  /** Hide column on screens smaller than md breakpoint. */
  hiddenOnMobile?: boolean;
}

// ---------------------------------------------------------------------------
// Sort state: null → asc → desc → null
// ---------------------------------------------------------------------------
type SortDir = "asc" | "desc" | null;

// ---------------------------------------------------------------------------
// Props (all new fields are optional for backward compat)
// ---------------------------------------------------------------------------
interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyFn: (row: T) => string | number;

  /** Show search input above table. */
  searchable?: boolean;
  searchPlaceholder?: string;

  /** Show pagination below table. */
  paginated?: boolean;
  defaultPageSize?: number;

  /** Callback when a row is clicked. */
  onRowClick?: (row: T) => void;

  /** Message shown when data array is empty (no search active). */
  emptyMessage?: string;
  /** Message shown when search produces no results. */
  emptyFilterMessage?: string;

  /** Make the header sticky when scrolling. */
  stickyHeader?: boolean;
  /** Alternate row background shading. */
  striped?: boolean;
  /** Reduce cell padding for denser layout. */
  compact?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract plain text from a ReactNode for search fallback. */
function nodeToText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeToText).join("");
  if (typeof node === "object" && "props" in node) {
    const props = (node as { props?: { children?: ReactNode } }).props;
    return nodeToText(props?.children);
  }
  return "";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function DataTable<T>({
  columns,
  data,
  keyFn,
  searchable = false,
  searchPlaceholder,
  paginated = false,
  defaultPageSize = 10,
  onRowClick,
  emptyMessage = "No data available",
  emptyFilterMessage = "No results match your search",
  stickyHeader = false,
  striped = false,
  compact = false,
}: DataTableProps<T>) {
  // -- Sort state -----------------------------------------------------------
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  // -- Search state ---------------------------------------------------------
  const [search, setSearch] = useState("");

  // -- Pagination state -----------------------------------------------------
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);

  // -- Sort cycle: null → asc → desc → null --------------------------------
  function toggleSort(key: string) {
    if (sortCol !== key) {
      setSortCol(key);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortCol(null);
      setSortDir(null);
    }
  }

  // -- Filter data by search ------------------------------------------------
  const searchLower = search.toLowerCase();

  const filtered = useMemo(() => {
    if (!searchable || !searchLower) return data;
    return data.filter((row) =>
      columns.some((col) => {
        const text = col.searchValue
          ? col.searchValue(row)
          : nodeToText(col.render(row));
        return text.toLowerCase().includes(searchLower);
      }),
    );
  }, [data, searchable, searchLower, columns]);

  // -- Sort filtered data ---------------------------------------------------
  const sorted = useMemo(() => {
    if (!sortCol || !sortDir) return filtered;
    const col = columns.find((c) => c.key === sortCol);
    if (!col?.sortValue) return filtered;
    const fn = col.sortValue;
    return [...filtered].sort((a, b) => {
      const va = fn(a);
      const vb = fn(b);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [filtered, sortCol, sortDir, columns]);

  // -- Paginate sorted data -------------------------------------------------
  const totalPages = paginated ? Math.max(1, Math.ceil(sorted.length / pageSize)) : 1;
  // Clamp page if data shrinks (e.g. after search)
  const safePage = Math.min(page, totalPages);
  if (safePage !== page) setPage(safePage);

  const visible = paginated
    ? sorted.slice((safePage - 1) * pageSize, safePage * pageSize)
    : sorted;

  // -- Handlers -------------------------------------------------------------
  const handlePageSizeChange = useCallback(
    (size: number) => {
      setPageSize(size);
      setPage(1);
    },
    [],
  );

  const handleSearchChange = useCallback((v: string) => {
    setSearch(v);
    setPage(1);
  }, []);

  const clearSearch = useCallback(() => {
    setSearch("");
    setPage(1);
  }, []);

  // -- Cell padding ---------------------------------------------------------
  const cellPad = compact ? "px-3 py-1.5" : "px-3 py-2.5";

  // -- Render ---------------------------------------------------------------
  return (
    <div className="space-y-3">
      {/* Search bar */}
      {searchable && (
        <TableSearch
          value={search}
          onChange={handleSearchChange}
          placeholder={searchPlaceholder}
        />
      )}

      {/* Table wrapper */}
      <div className="overflow-x-auto rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50">
        <table className="w-full text-sm table-auto">
          {/* Head */}
          <thead>
            <tr
              className={`border-b border-gray-800/50 bg-gray-900/30 ${
                stickyHeader ? "sticky top-0 z-10 bg-gray-900" : ""
              }`}
            >
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => col.sortValue && toggleSort(col.key)}
                  aria-sort={col.sortValue ? (sortCol === col.key ? (sortDir === "asc" ? "ascending" : sortDir === "desc" ? "descending" : "none") : "none") : undefined}
                  className={`${cellPad} text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold select-none ${
                    col.sortValue
                      ? "cursor-pointer hover:text-gray-300 transition-colors"
                      : ""
                  } ${col.hiddenOnMobile ? "hidden md:table-cell" : ""}`}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.header}
                    {col.sortValue && (
                      <span className="inline-flex flex-col leading-none text-[10px] -space-y-0.5">
                        <span
                          className={
                            sortCol === col.key && sortDir === "asc"
                              ? "text-accent-light"
                              : "text-gray-600"
                          }
                        >
                          &#9650;
                        </span>
                        <span
                          className={
                            sortCol === col.key && sortDir === "desc"
                              ? "text-accent-light"
                              : "text-gray-600"
                          }
                        >
                          &#9660;
                        </span>
                      </span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="text-center py-12">
                  {searchable && search ? (
                    <div className="flex flex-col items-center gap-2">
                      <p className="text-sm text-gray-400">
                        {emptyFilterMessage}
                      </p>
                      <button
                        onClick={clearSearch}
                        className="text-xs text-accent-light hover:text-accent transition-colors"
                      >
                        Clear search
                      </button>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-400">{emptyMessage}</p>
                  )}
                </td>
              </tr>
            ) : (
              visible.map((row, idx) => (
                <tr
                  key={keyFn(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={`border-b border-gray-800/30 hover:bg-gray-800/40 transition-colors ${
                    onRowClick ? "cursor-pointer" : ""
                  } ${striped && idx % 2 === 1 ? "bg-gray-900/30" : ""}`}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`${cellPad} whitespace-nowrap ${
                        col.hiddenOnMobile ? "hidden md:table-cell" : ""
                      }`}
                    >
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {paginated && sorted.length > 0 && (
        <Pagination
          currentPage={safePage}
          totalPages={totalPages}
          onPageChange={setPage}
          pageSize={pageSize}
          onPageSizeChange={handlePageSizeChange}
          totalItems={sorted.length}
        />
      )}
    </div>
  );
}
