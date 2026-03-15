import { usePageTitle } from "../hooks/usePageTitle";
import { Card, CardHeader, CardBody } from "../components/ui/Card";
import ThemeToggle from "../components/settings/ThemeToggle";
import NotificationPreferences from "../components/settings/NotificationPreferences";
import CacheSettings from "../components/settings/CacheSettings";
import RiskParametersCard from "../components/settings/RiskParametersCard";
import NotificationConfigCard from "../components/settings/NotificationConfigCard";
import SystemInfoCard from "../components/settings/SystemInfoCard";
import ExportHubCard from "../components/settings/ExportHubCard";

export default function SettingsPage() {
  usePageTitle("Settings");

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

      {/* -- Export Hub -- */}
      <ExportHubCard />

      {/* -- Risk Parameters -- */}
      <RiskParametersCard />

      {/* -- Notification Configuration -- */}
      <NotificationConfigCard />

      {/* -- System Info -- */}
      <SystemInfoCard />
    </div>
  );
}
