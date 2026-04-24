import { lazy, Suspense, useState } from "react";
import { Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import { ErrorBoundary } from "./components/ui/ErrorBoundary";
import { ToastContainer } from "./components/ui/Toast";
import { ToastProvider } from "./contexts/ToastContext";
import CommandPalette from "./components/ui/CommandPalette";
import { useHotkeys } from "./hooks/useHotkeys";
import { SkeletonCard, SkeletonTable } from "./components/ui/Skeleton";

// ---------------------------------------------------------------------------
// Route-based code splitting — each page is lazy-loaded on first visit
// ---------------------------------------------------------------------------
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const AnalyzePage = lazy(() => import("./pages/AnalyzePage"));
const PortfolioPage = lazy(() => import("./pages/PortfolioPage"));
const PositionDetailPage = lazy(() => import("./pages/PositionDetailPage"));
const PerformancePage = lazy(() => import("./pages/PerformancePage"));
const RiskPage = lazy(() => import("./pages/RiskPage"));
const WatchlistPage = lazy(() => import("./pages/WatchlistPage"));
const JournalPage = lazy(() => import("./pages/JournalPage"));
const BacktestPage = lazy(() => import("./pages/BacktestPage"));
const SignalsPage = lazy(() => import("./pages/SignalsPage"));
const MonitoringPage = lazy(() => import("./pages/MonitoringPage"));
const WeightsPage = lazy(() => import("./pages/WeightsPage"));
const CalibrationPage = lazy(() => import("./pages/CalibrationPage"));
const DaemonPage = lazy(() => import("./pages/DaemonPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const AnalysisHistoryPage = lazy(() => import("./pages/AnalysisHistoryPage"));

// ---------------------------------------------------------------------------
// Lazy-load fallback — matches the skeleton loading state used on pages
// ---------------------------------------------------------------------------
function PageFallback() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-48 rounded bg-gray-800 animate-pulse" />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
      <SkeletonTable rows={5} columns={6} />
    </div>
  );
}

function AppContent() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useHotkeys({
    "ctrl+k": () => setPaletteOpen(true),
    "meta+k": () => setPaletteOpen(true),
  });

  return (
    <AppShell>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/portfolio/:ticker" element={<PositionDetailPage />} />
          <Route path="/performance" element={<PerformancePage />} />
          <Route path="/risk" element={<RiskPage />} />
          <Route path="/watchlist" element={<WatchlistPage />} />
          <Route path="/journal" element={<JournalPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/signals" element={<SignalsPage />} />
          <Route path="/monitoring" element={<MonitoringPage />} />
          <Route path="/calibration" element={<CalibrationPage />} />
          <Route path="/weights" element={<WeightsPage />} />
          <Route path="/daemon" element={<DaemonPage />} />
          <Route path="/analysis-history" element={<AnalysisHistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Suspense>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <ToastContainer />
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
