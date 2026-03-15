import { Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import DashboardPage from "./pages/DashboardPage";
import AnalyzePage from "./pages/AnalyzePage";
import PortfolioPage from "./pages/PortfolioPage";
import PositionDetailPage from "./pages/PositionDetailPage";
import BacktestPage from "./pages/BacktestPage";
import SignalsPage from "./pages/SignalsPage";
import MonitoringPage from "./pages/MonitoringPage";
import WeightsPage from "./pages/WeightsPage";
import DaemonPage from "./pages/DaemonPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/portfolio/:ticker" element={<PositionDetailPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/signals" element={<SignalsPage />} />
        <Route path="/monitoring" element={<MonitoringPage />} />
        <Route path="/weights" element={<WeightsPage />} />
        <Route path="/daemon" element={<DaemonPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </AppShell>
  );
}
