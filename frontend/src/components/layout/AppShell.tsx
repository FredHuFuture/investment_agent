import { useState, useCallback } from "react";
import Sidebar from "./Sidebar";
import { useMobile } from "../../hooks/useMobile";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const isMobile = useMobile();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950 text-gray-100">
      {/* Mobile header bar */}
      {isMobile && (
        <header className="fixed inset-x-0 top-0 z-30 flex h-14 items-center border-b border-gray-800 bg-gray-900 px-4">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-2 text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors"
            aria-label="Open menu"
          >
            <svg
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
          </button>
          <span className="flex-1 text-center text-sm font-semibold text-white tracking-tight">
            Investment Agent
          </span>
          {/* Spacer to balance hamburger button */}
          <div className="w-9" />
        </header>
      )}

      {/* Backdrop (mobile only) */}
      {isMobile && sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 transition-opacity"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={closeSidebar}
        isMobile={isMobile}
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
      />

      {/* Main content */}
      <main
        className={`flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 ${
          isMobile ? "pt-20" : ""
        }`}
      >
        {children}
      </main>
    </div>
  );
}
