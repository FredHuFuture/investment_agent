import { Routes, Route } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import DashboardPage from "./pages/DashboardPage";
import AnalyzePage from "./pages/AnalyzePage";
import PortfolioPage from "./pages/PortfolioPage";
import BacktestPage from "./pages/BacktestPage";
import SignalsPage from "./pages/SignalsPage";
import MonitoringPage from "./pages/MonitoringPage";
import WeightsPage from "./pages/WeightsPage";
import DaemonPage from "./pages/DaemonPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/signals" element={<SignalsPage />} />
        <Route path="/monitoring" element={<MonitoringPage />} />
        <Route path="/weights" element={<WeightsPage />} />
        <Route path="/daemon" element={<DaemonPage />} />
      </Routes>
    </AppShell>
  );
}
