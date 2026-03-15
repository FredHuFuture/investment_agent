import { useState } from "react";
import { usePageTitle } from "../hooks/usePageTitle";
import { Card, CardHeader, CardBody } from "../components/ui/Card";
import { TextInput } from "../components/ui/Input";
import ThemeToggle from "../components/settings/ThemeToggle";
import NotificationPreferences from "../components/settings/NotificationPreferences";
import CacheSettings from "../components/settings/CacheSettings";
import RiskParametersCard from "../components/settings/RiskParametersCard";
import NotificationConfigCard from "../components/settings/NotificationConfigCard";
import SystemInfoCard from "../components/settings/SystemInfoCard";

export default function SettingsPage() {
  usePageTitle("Settings");
  const [signalTicker, setSignalTicker] = useState("");

  const signalExportUrl = signalTicker.trim()
    ? `/api/export/signals/csv?ticker=${encodeURIComponent(signalTicker.trim())}`
    : "/api/export/signals/csv";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* -- Appearance -- */}
      <Card>
        <CardHeader title="Appearance" subtitle="Choose your preferred theme" />
        <CardBody>
          <ThemeToggle />
        </CardBody>
      </Card>

      {/* -- Notifications -- */}
      <Card>
        <CardHeader title="Notifications" subtitle="Configure notification channels" />
        <CardBody>
          <NotificationPreferences />
        </CardBody>
      </Card>

      {/* -- Data & Cache -- */}
      <Card>
        <CardHeader title="Data & Cache" subtitle="Manage cache TTL and clear cached data" />
        <CardBody>
          <CacheSettings />
        </CardBody>
      </Card>

      {/* -- Export -- */}
      <Card>
        <CardHeader title="Export" subtitle="Download your data" />
        <CardBody>
          <div className="space-y-4">
            <div>
              <h3 className="text-xs font-medium text-gray-400 mb-3">Quick Downloads</h3>
              <div className="flex flex-wrap gap-2">
                <a
                  href="/api/export/portfolio/csv"
                  download
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-medium text-gray-300 transition-colors inline-block"
                >
                  Portfolio CSV
                </a>
                <a
                  href="/api/export/trades/csv"
                  download
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-medium text-gray-300 transition-colors inline-block"
                >
                  Trade Journal CSV
                </a>
                <a
                  href="/api/export/portfolio/report"
                  download
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-medium text-gray-300 transition-colors inline-block"
                >
                  Full Report
                </a>
                <a
                  href="/api/export/signals/csv"
                  download
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-medium text-gray-300 transition-colors inline-block"
                >
                  All Signals CSV
                </a>
              </div>
            </div>

            <div className="border-t border-gray-800/50 pt-4">
              <h3 className="text-xs font-medium text-gray-400 mb-3">Signal History Export</h3>
              <div className="flex items-center gap-2">
                <TextInput
                  value={signalTicker}
                  onChange={(e) => setSignalTicker(e.target.value.toUpperCase())}
                  placeholder="Filter by ticker"
                  className="w-52"
                />
                <a
                  href={signalExportUrl}
                  download
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-medium text-gray-300 transition-colors inline-block"
                >
                  Download Signals
                </a>
              </div>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* -- Risk Parameters -- */}
      <RiskParametersCard />

      {/* -- Notification Configuration -- */}
      <NotificationConfigCard />

      {/* -- System Info -- */}
      <SystemInfoCard />
    </div>
  );
}
