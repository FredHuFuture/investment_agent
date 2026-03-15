import { useMemo } from "react";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  pageSize: number;
  onPageSizeChange?: (size: number) => void;
  totalItems: number;
  pageSizeOptions?: number[];
}

/** Build the page-number array: always first, last, current +/- 1, with ellipsis gaps. */
function getPageNumbers(current: number, total: number): (number | "...")[] {
  if (total <= 5) return Array.from({ length: total }, (_, i) => i + 1);

  const pages = new Set<number>();
  pages.add(1);
  pages.add(total);
  for (let i = current - 1; i <= current + 1; i++) {
    if (i >= 1 && i <= total) pages.add(i);
  }

  const sorted = [...pages].sort((a, b) => a - b);
  const result: (number | "...")[] = [];
  for (let i = 0; i < sorted.length; i++) {
    const prev = sorted[i - 1];
    const cur = sorted[i]!;
    if (prev != null && cur - prev > 1) result.push("...");
    result.push(cur);
  }
  return result;
}

const btnBase =
  "min-w-[36px] h-9 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

export default function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  pageSize,
  onPageSizeChange,
  totalItems,
  pageSizeOptions = [10, 25, 50],
}: PaginationProps) {
  const pages = useMemo(
    () => getPageNumbers(currentPage, totalPages),
    [currentPage, totalPages],
  );

  const start = (currentPage - 1) * pageSize + 1;
  const end = Math.min(currentPage * pageSize, totalItems);

  return (
    <nav aria-label="Pagination navigation">
    <div className="flex flex-col sm:flex-row justify-between items-center gap-3 px-2 py-3">
      {/* Left: item range */}
      <span className="text-sm text-gray-400">
        Showing {start}-{end} of {totalItems} items
      </span>

      {/* Center: page buttons */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage <= 1}
          className={`${btnBase} bg-gray-800 hover:bg-gray-700 text-gray-300`}
          aria-label="First page"
        >
          &laquo;
        </button>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className={`${btnBase} bg-gray-800 hover:bg-gray-700 text-gray-300`}
          aria-label="Previous page"
        >
          &lsaquo;
        </button>

        {pages.map((p, i) =>
          p === "..." ? (
            <span key={`ellipsis-${i}`} className="px-1 text-gray-500">
              &hellip;
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              aria-current={p === currentPage ? "page" : undefined}
              className={`${btnBase} ${
                p === currentPage
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 hover:bg-gray-700 text-gray-300"
              }`}
            >
              {p}
            </button>
          ),
        )}

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className={`${btnBase} bg-gray-800 hover:bg-gray-700 text-gray-300`}
          aria-label="Next page"
        >
          &rsaquo;
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage >= totalPages}
          className={`${btnBase} bg-gray-800 hover:bg-gray-700 text-gray-300`}
          aria-label="Last page"
        >
          &raquo;
        </button>
      </div>

      {/* Right: page-size selector */}
      {onPageSizeChange && (
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <span>Rows per page</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="bg-gray-800 border border-gray-700 rounded-lg px-2 py-1 text-gray-300 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {pageSizeOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
    </nav>
  );
}
