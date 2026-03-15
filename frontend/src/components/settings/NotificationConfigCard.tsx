import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";
import { TextInput } from "../ui/Input";
import { useApi } from "../../hooks/useApi";
import { useToast } from "../../contexts/ToastContext";
import {
  getNotificationConfig,
  saveNotificationConfig,
} from "../../api/endpoints";
import type { NotificationConfig } from "../../api/types";

const DEFAULTS: NotificationConfig = {
  smtp_host: "",
  smtp_port: 587,
  smtp_user: "",
  smtp_password: "",
  smtp_enabled: false,
  telegram_bot_token: "",
  telegram_chat_id: "",
  telegram_enabled: false,
  notify_critical: true,
  notify_high: true,
  notify_warning: false,
  notify_info: false,
};

const SEVERITY_FILTERS: {
  key: keyof NotificationConfig;
  label: string;
}[] = [
  { key: "notify_critical", label: "Critical" },
  { key: "notify_high", label: "High" },
  { key: "notify_warning", label: "Warning" },
  { key: "notify_info", label: "Info" },
];

export default function NotificationConfigCard() {
  const { data, loading } = useApi(getNotificationConfig, {
    cacheKey: "notification_config",
    ttlMs: 60_000,
  });

  const { toast } = useToast();
  const [config, setConfig] = useState<NotificationConfig>(DEFAULTS);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (data) {
      setConfig(data);
    }
  }, [data]);

  const update = useCallback(
    <K extends keyof NotificationConfig>(
      key: K,
      value: NotificationConfig[K],
    ) => {
      setConfig((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await saveNotificationConfig(config);
      setConfig(res.data);
      toast.success("Saved", "Notification configuration updated");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      toast.error("Error", msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading && !data) {
    return null;
  }

  return (
    <Card>
      <CardHeader
        title="Notification Configuration"
        subtitle="Email, Telegram, and alert severity filters"
      />
      <CardBody>
        <div className="space-y-6">
          {/* ---------- Email (SMTP) ---------- */}
          <div>
            <h3 className="text-xs font-medium text-gray-400 mb-3">
              Email (SMTP)
            </h3>
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <TextInput
                  label="SMTP Host"
                  value={config.smtp_host}
                  onChange={(e) => update("smtp_host", e.target.value)}
                  placeholder="smtp.example.com"
                />
                <TextInput
                  label="SMTP Port"
                  type="number"
                  value={String(config.smtp_port)}
                  onChange={(e) =>
                    update("smtp_port", parseInt(e.target.value, 10) || 587)
                  }
                  placeholder="587"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <TextInput
                  label="Username"
                  value={config.smtp_user}
                  onChange={(e) => update("smtp_user", e.target.value)}
                  placeholder="user@example.com"
                />
                <TextInput
                  label="Password"
                  type="password"
                  value={config.smtp_password}
                  onChange={(e) => update("smtp_password", e.target.value)}
                  placeholder="••••••••"
                />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.smtp_enabled}
                  onChange={(e) => update("smtp_enabled", e.target.checked)}
                  className="h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
                />
                <span className="text-xs text-gray-300">Enable Email Notifications</span>
              </label>
            </div>
          </div>

          {/* ---------- Telegram ---------- */}
          <div className="border-t border-gray-800/50 pt-5">
            <h3 className="text-xs font-medium text-gray-400 mb-3">
              Telegram
            </h3>
            <div className="space-y-3">
              <TextInput
                label="Bot Token"
                value={config.telegram_bot_token}
                onChange={(e) => update("telegram_bot_token", e.target.value)}
                placeholder="123456:ABC-DEF..."
              />
              <TextInput
                label="Chat ID"
                value={config.telegram_chat_id}
                onChange={(e) => update("telegram_chat_id", e.target.value)}
                placeholder="-1001234567890"
              />
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.telegram_enabled}
                  onChange={(e) => update("telegram_enabled", e.target.checked)}
                  className="h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
                />
                <span className="text-xs text-gray-300">Enable Telegram Notifications</span>
              </label>
            </div>
          </div>

          {/* ---------- Alert Severity Filters ---------- */}
          <div className="border-t border-gray-800/50 pt-5">
            <h3 className="text-xs font-medium text-gray-400 mb-3">
              Alert Severity Filters
            </h3>
            <div className="flex flex-wrap gap-4">
              {SEVERITY_FILTERS.map(({ key, label }) => (
                <label
                  key={key}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={config[key] as boolean}
                    onChange={(e) =>
                      update(key, e.target.checked as NotificationConfig[typeof key])
                    }
                    className="h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
                  />
                  <span className="text-xs text-gray-300">{label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* ---------- Save ---------- */}
          <div className="border-t border-gray-800/50 pt-4 flex justify-end">
            <Button
              variant="primary"
              size="sm"
              loading={saving}
              onClick={handleSave}
            >
              Save Configuration
            </Button>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
