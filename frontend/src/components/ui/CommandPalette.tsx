import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon?: React.ReactNode;
  action: () => void;
  category: "page" | "action" | "ticker";
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

/* ------------------------------------------------------------------ */
/* Small inline icons                                                  */
/* ------------------------------------------------------------------ */

function PageIcon() {
  return (
    <svg className="w-5 h-5 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16v16H4z" />
      <path d="M4 9h16" />
    </svg>
  );
}

function ActionIcon() {
  return (
    <svg className="w-5 h-5 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="w-5 h-5 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Fuzzy match: every word in query must appear in text                 */
/* ------------------------------------------------------------------ */

function fuzzyMatch(query: string, text: string): boolean {
  const lower = text.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => lower.includes(word));
}

/* ------------------------------------------------------------------ */
/* Category labels                                                     */
/* ------------------------------------------------------------------ */

const CATEGORY_LABELS: Record<string, string> = {
  page: "Pages",
  action: "Actions",
  ticker: "Tickers",
};

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Close helper that also resets state
  const close = useCallback(() => {
    setQuery("");
    setSelectedIndex(0);
    onClose();
  }, [onClose]);

  // Build command items
  const commands = useMemo<CommandItem[]>(() => {
    const pages: CommandItem[] = [
      { id: "p-dashboard",   label: "Dashboard",   description: "Overview & key metrics",     category: "page", action: () => { navigate("/"); close(); } },
      { id: "p-analyze",     label: "Analyze",     description: "Run stock analysis",         category: "page", action: () => { navigate("/analyze"); close(); } },
      { id: "p-portfolio",   label: "Portfolio",   description: "Current positions",          category: "page", action: () => { navigate("/portfolio"); close(); } },
      { id: "p-performance", label: "Performance", description: "Returns & PnL tracking",     category: "page", action: () => { navigate("/performance"); close(); } },
      { id: "p-watchlist",   label: "Watchlist",   description: "Tracked tickers",            category: "page", action: () => { navigate("/watchlist"); close(); } },
      { id: "p-backtest",    label: "Backtest",    description: "Historical strategy testing", category: "page", action: () => { navigate("/backtest"); close(); } },
      { id: "p-signals",     label: "Signals",     description: "Buy/sell signal history",    category: "page", action: () => { navigate("/signals"); close(); } },
      { id: "p-monitoring",  label: "Monitoring",  description: "System health & alerts",     category: "page", action: () => { navigate("/monitoring"); close(); } },
      { id: "p-weights",     label: "Weights",     description: "Model weight configuration", category: "page", action: () => { navigate("/weights"); close(); } },
      { id: "p-daemon",      label: "Daemon",      description: "Background service control", category: "page", action: () => { navigate("/daemon"); close(); } },
      { id: "p-settings",    label: "Settings",    description: "App configuration",          category: "page", action: () => { navigate("/settings"); close(); } },
    ];
    const actions: CommandItem[] = [
      { id: "a-run-analysis",   label: "Run Analysis",    description: "Navigate to analyze page",  category: "action", icon: <ActionIcon />, action: () => { navigate("/analyze"); close(); } },
      { id: "a-health-check",   label: "Run Health Check", description: "Navigate to monitoring",   category: "action", icon: <ActionIcon />, action: () => { navigate("/monitoring"); close(); } },
      { id: "a-export-portfolio", label: "Export Portfolio", description: "Navigate to settings",    category: "action", icon: <ActionIcon />, action: () => { navigate("/settings"); close(); } },
    ];
    return [...pages, ...actions];
  }, [navigate, close]);

  // Filtered results
  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    return commands.filter(
      (cmd) =>
        fuzzyMatch(query, cmd.label) ||
        (cmd.description && fuzzyMatch(query, cmd.description)),
    );
  }, [commands, query]);

  // Group by category
  const grouped = useMemo(() => {
    const map = new Map<string, CommandItem[]>();
    for (const item of filtered) {
      const existing = map.get(item.category);
      if (existing) {
        existing.push(item);
      } else {
        map.set(item.category, [item]);
      }
    }
    return map;
  }, [filtered]);

  // Flat list for keyboard nav
  const flatList = useMemo(() => {
    const result: CommandItem[] = [];
    for (const items of grouped.values()) {
      result.push(...items);
    }
    return result;
  }, [grouped]);

  // Reset selection when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return;
    const selected = listRef.current.querySelector("[data-selected='true']");
    selected?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => (i + 1) % Math.max(flatList.length, 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) =>
          i <= 0 ? Math.max(flatList.length - 1, 0) : i - 1,
        );
      } else if (e.key === "Enter") {
        e.preventDefault();
        flatList[selectedIndex]?.action();
      } else if (e.key === "Escape") {
        close();
      }
    },
    [flatList, selectedIndex, close],
  );

  if (!open) return null;

  let flatIdx = -1;

  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 backdrop-blur-sm"
      onClick={close}
    >
      <div
        className="max-w-lg mx-auto mt-[15vh] bg-gray-900 border border-gray-700 rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 border-b border-gray-800">
          <SearchIcon />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages & actions..."
            className="flex-1 text-lg py-3 bg-transparent text-gray-100 placeholder-gray-600 outline-none"
          />
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-[360px] overflow-y-auto">
          {flatList.length === 0 ? (
            <div className="px-4 py-8 text-center text-gray-500 text-sm">
              No results found
            </div>
          ) : (
            Array.from(grouped.entries()).map(([category, items]) => (
              <div key={category}>
                <div className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  {CATEGORY_LABELS[category] ?? category}
                </div>
                {items.map((item) => {
                  flatIdx++;
                  const isSelected = flatIdx === selectedIndex;
                  return (
                    <button
                      key={item.id}
                      data-selected={isSelected}
                      onClick={() => item.action()}
                      className={`w-full px-4 py-3 flex items-center gap-3 cursor-pointer text-left transition-colors ${
                        isSelected ? "bg-gray-800/80" : "hover:bg-gray-800"
                      }`}
                    >
                      <span className="shrink-0">
                        {item.icon ?? <PageIcon />}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="text-gray-100 font-medium">
                          {item.label}
                        </span>
                        {item.description && (
                          <span className="ml-2 text-gray-500 text-sm">
                            {item.description}
                          </span>
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-600 flex items-center gap-4">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>Esc Close</span>
        </div>
      </div>
    </div>
  );
}
