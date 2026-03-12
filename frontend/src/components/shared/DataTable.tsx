import { useState, useMemo, type ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => number | string;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  keyFn: (row: T) => string | number;
}

export default function DataTable<T>({ columns, data, keyFn }: Props<T>) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  const sorted = useMemo(() => {
    if (!sortCol) return data;
    const col = columns.find((c) => c.key === sortCol);
    if (!col?.sortValue) return data;
    const fn = col.sortValue;
    return [...data].sort((a, b) => {
      const va = fn(a);
      const vb = fn(b);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sortAsc ? cmp : -cmp;
    });
  }, [data, sortCol, sortAsc, columns]);

  function toggleSort(key: string) {
    if (sortCol === key) setSortAsc(!sortAsc);
    else {
      setSortCol(key);
      setSortAsc(true);
    }
  }

  return (
    <div className="overflow-x-auto rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800/50 bg-gray-900/30">
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => col.sortValue && toggleSort(col.key)}
                className={`px-3 py-2.5 text-left text-[11px] uppercase tracking-wider text-gray-500 font-semibold select-none ${
                  col.sortValue
                    ? "cursor-pointer hover:text-gray-300 transition-colors"
                    : ""
                }`}
              >
                {col.header}
                {sortCol === col.key && (
                  <span className="ml-1 text-gray-400">
                    {sortAsc ? "↑" : "↓"}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={keyFn(row)}
              className="border-b border-gray-800/30 hover:bg-gray-800/20 transition-colors"
            >
              {columns.map((col) => (
                <td key={col.key} className="px-3 py-2.5 whitespace-nowrap">
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
