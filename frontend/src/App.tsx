import { useState } from "react";
import { Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import { ToastProvider } from "./contexts/ToastContext";
import CommandPalette from "./components/ui/CommandPalette";
import { useHotkeys } from "./hooks/useHotkeys";
import DashboardPage from "./pages/DashboardPage";
import AnalyzePage from "./pages/AnalyzePage";
import PortfolioPage from "./pages/PortfolioPage";
import PositionDetailPage from "./pages/PositionDetailPage";
import BacktestPage from "./pages/BacktestPage";
import SignalsPage from "./pages/SignalsPage";
import MonitoringPage from "./pages/MonitoringPage";
import WeightsPage from "./pages/WeightsPage";
import DaemonPage from "./pages/DaemonPage";
import PerformancePage from "./pages/PerformancePage";
import WatchlistPage from "./pages/WatchlistPage";
import SettingsPage from "./pages/SettingsPage";

function AppContent() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useHotkeys({
    "ctrl+k": () => setPaletteOpen(true),
    "meta+k": () => setPaletteOpen(true),
  });

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/portfolio/:ticker" element={<PositionDetailPage />} />
        <Route path="/performance" element={<PerformancePage />} />
        <Route path="/watchlist" element={<WatchlistPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/signals" element={<SignalsPage />} />
        <Route path="/monitoring" element={<MonitoringPage />} />
        <Route path="/weights" element={<WeightsPage />} />
        <Route path="/daemon" element={<DaemonPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </AppShell>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AppContent />
      </ToastProvider>
    </ErrorBoundary>
  );
}
