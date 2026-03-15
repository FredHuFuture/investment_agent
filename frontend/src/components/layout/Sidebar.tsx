import { NavLink } from "react-router-dom";

// ---------------------------------------------------------------------------
// Inline SVG icons — no external dependency
// ---------------------------------------------------------------------------
function Icon({ d, className }: { d: string; className?: string }) {
  return (
    <svg
      className={className ?? "w-[18px] h-[18px]"}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={d} />
    </svg>
  );
}

// Multi-path icon for more complex shapes
function MultiIcon({
  paths,
  className,
}: {
  paths: string[];
  className?: string;
}) {
  return (
    <svg
      className={className ?? "w-[18px] h-[18px]"}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths.map((d, i) => (
        <path key={i} d={d} />
      ))}
    </svg>
  );
}

// Heroicons / Lucide-inspired paths
const NAV_ICONS: Record<string, () => JSX.Element> = {
  // Dashboard — grid of 4 squares
  Dashboard: () => (
    <MultiIcon
      paths={[
        "M3 3h7v7H3z",
        "M14 3h7v7h-7z",
        "M3 14h7v7H3z",
        "M14 14h7v7h-7z",
      ]}
    />
  ),
  // Analysis — magnifying glass with chart
  Analysis: () => (
    <MultiIcon
      paths={[
        "M21 21l-4.35-4.35",
        "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z",
        "M8 11h6",
        "M11 8v6",
      ]}
    />
  ),
  // Portfolio — briefcase
  Portfolio: () => (
    <MultiIcon
      paths={[
        "M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z",
        "M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2",
      ]}
    />
  ),
  // Backtest — rewind / history clock
  Backtest: () => (
    <MultiIcon
      paths={[
        "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8",
        "M3 3v5h5",
        "M12 7v5l4 2",
      ]}
    />
  ),
  // Signals — lightning bolt
  Signals: () => <Icon d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />,
  // Monitoring — bell
  Monitoring: () => (
    <MultiIcon
      paths={[
        "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9",
        "M13.73 21a2 2 0 0 1-3.46 0",
      ]}
    />
  ),
  // Weights — scale / balance
  Weights: () => (
    <MultiIcon
      paths={[
        "M12 3v18",
        "M5 8l7-5 7 5",
        "M5 8l-2 8h6L7 8",
        "M19 8l-2 8h6l-2-8",
      ]}
    />
  ),
  // Daemon — cog / gear
  Daemon: () => (
    <MultiIcon
      paths={[
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
        "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
      ]}
    />
  ),
  // Watchlist — eye icon
  Watchlist: () => (
    <MultiIcon
      paths={[
        "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z",
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
      ]}
    />
  ),
  // Performance — trending-up chart
  Performance: () => (
    <MultiIcon
      paths={[
        "M22 12l-4-4-6 6-4-4-6 6",
        "M22 6v6h-6",
      ]}
    />
  ),
  // Risk — warning triangle
  Risk: () => (
    <MultiIcon
      paths={[
        "M12 9v4",
        "M12 17h.01",
        "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z",
      ]}
    />
  ),
  // Journal — book / notebook
  Journal: () => (
    <MultiIcon
      paths={[
        "M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20",
      ]}
    />
  ),
  // Settings — sliders / adjustments
  Settings: () => (
    <MultiIcon
      paths={[
        "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z",
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
      ]}
    />
  ),
};

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/analyze", label: "Analysis" },
  { to: "/portfolio", label: "Portfolio" },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/performance", label: "Performance" },
  { to: "/risk", label: "Risk" },
  { to: "/journal", label: "Journal" },
  { to: "/backtest", label: "Backtest" },
  { to: "/signals", label: "Signals" },
  { to: "/monitoring", label: "Monitoring" },
  { to: "/weights", label: "Weights" },
  { to: "/daemon", label: "Daemon" },
  { to: "/settings", label: "Settings" },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  isMobile: boolean;
  collapsed: boolean;
  onToggle: () => void;
}

export default function Sidebar({
  isOpen,
  onClose,
  isMobile,
  collapsed,
  onToggle,
}: SidebarProps) {
  // On mobile: always expanded (w-64), positioned fixed with slide transform
  // On desktop: collapsible (w-16 / w-56), normal flow
  const asideClasses = isMobile
    ? [
        "fixed inset-y-0 left-0 z-50 w-64",
        "bg-gray-900 border-r border-gray-800/40 flex flex-col",
        "transition-transform duration-300 ease-in-out",
        isOpen ? "translate-x-0" : "-translate-x-full",
      ].join(" ")
    : [
        "shrink-0 bg-gray-900/80 border-r border-gray-800/40 flex flex-col backdrop-blur-sm transition-all duration-200",
        collapsed ? "w-16" : "w-56",
      ].join(" ");

  const showLabels = isMobile ? true : !collapsed;

  return (
    <aside className={asideClasses}>
      {/* Header: logo + toggle */}
      <div
        className={`flex items-center ${
          !isMobile && collapsed
            ? "justify-center px-2 pt-4 pb-3"
            : "px-4 pt-4 pb-3"
        }`}
      >
        {showLabels && (
          <div className="flex items-center gap-2.5 flex-1 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
              <svg
                className="w-4.5 h-4.5 text-white"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </div>
            <span className="text-[15px] font-semibold text-white tracking-tight truncate">
              Investment Agent
            </span>
          </div>
        )}

        {/* Close button on mobile, collapse toggle on desktop */}
        {isMobile ? (
          <button
            onClick={onClose}
            className="ml-auto p-1.5 rounded-md text-gray-500 hover:text-gray-300 hover:bg-gray-800/50 transition-colors"
            aria-label="Close sidebar"
          >
            <svg
              className="w-5 h-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        ) : (
          <button
            onClick={onToggle}
            className={`p-1.5 rounded-md text-gray-500 hover:text-gray-300 hover:bg-gray-800/50 transition-colors ${
              collapsed ? "" : "ml-1 shrink-0"
            }`}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <svg
              className={`w-4 h-4 transition-transform duration-200 ${
                collapsed ? "rotate-180" : ""
              }`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M11 17l-5-5 5-5" />
              <path d="M18 17l-5-5 5-5" />
            </svg>
          </button>
        )}
      </div>

      {/* Divider */}
      <div
        className={`border-b border-gray-800/50 ${
          !isMobile && collapsed ? "mx-2" : "mx-4"
        }`}
      />

      {/* Navigation */}
      <nav
        className={`flex-1 pt-3 space-y-0.5 ${
          !isMobile && collapsed ? "px-2" : "px-3"
        }`}
      >
        {links.map((l) => {
          const IconComponent = NAV_ICONS[l.label];
          return (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              title={!isMobile && collapsed ? l.label : undefined}
              onClick={isMobile ? onClose : undefined}
              className={({ isActive }) =>
                [
                  "group flex items-center rounded-lg text-[13px] font-medium transition-all duration-150",
                  !isMobile && collapsed
                    ? "justify-center px-0 py-2.5"
                    : "gap-3 px-3 py-2",
                  isActive
                    ? "bg-blue-500/15 text-blue-400 border-l-[3px] border-blue-500"
                    : "text-gray-500 hover:text-gray-200 hover:bg-gray-800/40 border-l-[3px] border-transparent",
                ].join(" ")
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`transition-colors duration-150 shrink-0 ${
                      isActive
                        ? "text-blue-400"
                        : "text-gray-600 group-hover:text-gray-400"
                    }`}
                  >
                    {IconComponent && <IconComponent />}
                  </span>
                  {showLabels && <span>{l.label}</span>}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      {showLabels && (
        <div className="px-5 py-3 text-[10px] text-gray-700 text-center">
          v4 · Phase 2
        </div>
      )}
    </aside>
  );
}
