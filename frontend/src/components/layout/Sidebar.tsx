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

const NAV_ICONS: Record<string, () => JSX.Element> = {
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
  Portfolio: () => (
    <MultiIcon
      paths={[
        "M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z",
        "M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2",
      ]}
    />
  ),
  Watchlist: () => (
    <MultiIcon
      paths={[
        "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z",
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
      ]}
    />
  ),
  Performance: () => (
    <MultiIcon paths={["M22 12l-4-4-6 6-4-4-6 6", "M22 6v6h-6"]} />
  ),
  Risk: () => (
    <MultiIcon
      paths={[
        "M12 9v4",
        "M12 17h.01",
        "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z",
      ]}
    />
  ),
  Journal: () => (
    <MultiIcon
      paths={[
        "M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20",
      ]}
    />
  ),
  Backtest: () => (
    <MultiIcon
      paths={[
        "M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8",
        "M3 3v5h5",
        "M12 7v5l4 2",
      ]}
    />
  ),
  Signals: () => <Icon d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />,
  History: () => (
    <MultiIcon
      paths={[
        "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z",
        "M14 2v6h6",
        "M16 13H8",
        "M16 17H8",
        "M10 9H8",
      ]}
    />
  ),
  Monitoring: () => (
    <MultiIcon
      paths={[
        "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9",
        "M13.73 21a2 2 0 0 1-3.46 0",
      ]}
    />
  ),
  Calibration: () => (
    <MultiIcon
      paths={[
        "M2 12h4",
        "M18 12h4",
        "M12 2v4",
        "M12 18v4",
        "M12 12m-3 0a3 3 0 1 0 6 0 3 3 0 0 0-6 0",
        "M4.93 4.93l2.83 2.83",
        "M16.24 16.24l2.83 2.83",
      ]}
    />
  ),
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
  Daemon: () => (
    <MultiIcon
      paths={[
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
        "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
      ]}
    />
  ),
  Settings: () => (
    <MultiIcon
      paths={[
        "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z",
        "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
      ]}
    />
  ),
};

// ---------------------------------------------------------------------------
// Grouped navigation — editorial information architecture
// ---------------------------------------------------------------------------
interface NavItem {
  to: string;
  label: string;
  icon: string;
}

interface NavGroup {
  label?: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    items: [{ to: "/", label: "Dashboard", icon: "Dashboard" }],
  },
  {
    label: "Research",
    items: [
      { to: "/analyze", label: "Analysis", icon: "Analysis" },
      { to: "/watchlist", label: "Watchlist", icon: "Watchlist" },
      { to: "/signals", label: "Signals", icon: "Signals" },
      { to: "/analysis-history", label: "History", icon: "History" },
    ],
  },
  {
    label: "Portfolio",
    items: [
      { to: "/portfolio", label: "Portfolio", icon: "Portfolio" },
      { to: "/performance", label: "Performance", icon: "Performance" },
      { to: "/risk", label: "Risk", icon: "Risk" },
      { to: "/journal", label: "Journal", icon: "Journal" },
    ],
  },
  {
    label: "Tools",
    items: [
      { to: "/backtest", label: "Backtest", icon: "Backtest" },
      { to: "/calibration", label: "Calibration", icon: "Calibration" },
      { to: "/weights", label: "Weights", icon: "Weights" },
      { to: "/monitoring", label: "Monitoring", icon: "Monitoring" },
      { to: "/daemon", label: "Daemon", icon: "Daemon" },
    ],
  },
];

// ---------------------------------------------------------------------------
// Sidebar component
// ---------------------------------------------------------------------------
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
  const asideClasses = isMobile
    ? [
        "fixed inset-y-0 left-0 z-50 w-64",
        "bg-gray-950 border-r border-gray-800/40 flex flex-col",
        "transition-transform duration-300 ease-out",
        isOpen ? "translate-x-0" : "-translate-x-full",
      ].join(" ")
    : [
        "shrink-0 bg-gray-950 border-r border-gray-800/40 flex flex-col transition-all duration-200",
        collapsed ? "w-16" : "w-56",
      ].join(" ");

  const showLabels = isMobile ? true : !collapsed;

  function renderNavItem(item: NavItem) {
    const IconComponent = NAV_ICONS[item.icon];
    return (
      <NavLink
        key={item.to}
        to={item.to}
        end={item.to === "/"}
        title={!showLabels ? item.label : undefined}
        onClick={isMobile ? onClose : undefined}
        className={({ isActive }) =>
          [
            "group flex items-center rounded-lg text-[13px] font-medium transition-all duration-150",
            !showLabels
              ? "justify-center px-0 py-2.5"
              : "gap-2.5 px-3 py-[7px]",
            isActive
              ? "bg-accent/10 text-accent"
              : "text-gray-500 hover:text-gray-200 hover:bg-gray-800/40",
          ].join(" ")
        }
      >
        {({ isActive }) => (
          <>
            <span
              className={`transition-colors duration-150 shrink-0 ${
                isActive
                  ? "text-accent"
                  : "text-gray-600 group-hover:text-gray-400"
              }`}
            >
              {IconComponent && <IconComponent />}
            </span>
            {showLabels && <span>{item.label}</span>}
          </>
        )}
      </NavLink>
    );
  }

  return (
    <aside className={asideClasses}>
      {/* Header: Logo + toggle */}
      <div
        className={`flex items-center ${
          !isMobile && collapsed
            ? "justify-center px-2 pt-5 pb-4"
            : "px-4 pt-5 pb-4"
        }`}
      >
        {showLabels ? (
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <span className="font-display text-[22px] font-bold text-accent tracking-tight">
              Grip
            </span>
          </div>
        ) : (
          <span className="font-display text-lg font-bold text-accent">
            G
          </span>
        )}

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
              collapsed ? "" : "ml-auto shrink-0"
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

      {/* Navigation groups */}
      <nav
        className={`flex-1 overflow-y-auto pt-1 pb-4 ${
          !isMobile && collapsed ? "px-2" : "px-3"
        }`}
      >
        {navGroups.map((group, gi) => (
          <div key={gi} className={gi > 0 ? "mt-5" : ""}>
            {group.label && showLabels && (
              <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-gray-600">
                {group.label}
              </div>
            )}
            {group.label && !showLabels && (
              <div className="mx-auto mb-1.5 w-5 border-t border-gray-800/50" />
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => renderNavItem(item))}
            </div>
          </div>
        ))}
      </nav>

      {/* Settings — pinned at bottom */}
      <div
        className={`border-t border-gray-800/40 ${
          !isMobile && collapsed ? "px-2 py-3" : "px-3 py-3"
        }`}
      >
        {renderNavItem({ to: "/settings", label: "Settings", icon: "Settings" })}
      </div>
    </aside>
  );
}
