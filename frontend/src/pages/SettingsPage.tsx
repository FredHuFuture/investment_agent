import { useState } from "react";
import { testEmailNotification, testTelegramNotification } from "../api/endpoints";
import { usePageTitle } from "../hooks/usePageTitle";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { TextInput } from "../components/ui/Input";
import { useToast } from "../contexts/ToastContext";

export default function SettingsPage() {
  usePageTitle("Settings");
  const { toast } = useToast();
  const [emailLoading, setEmailLoading] = useState(false);
  const [telegramLoading, setTelegramLoading] = useState(false);
  const [signalTicker, setSignalTicker] = useState("");

  async function handleTestEmail() {
    setEmailLoading(true);
    try {
      const res = await testEmailNotification();
      if (res.data.sent) {
        toast.success("Test email sent");
      } else {
        toast.error("Email test failed", res.data.message ?? "Failed to send test email.");
      }
    } catch (err) {
      toast.error("Email test failed", err instanceof Error ? err.message : "Failed to send test email.");
    } finally {
      setEmailLoading(false);
    }
  }

  async function handleTestTelegram() {
    setTelegramLoading(true);
    try {
      const res = await testTelegramNotification();
      if (res.data.sent) {
        toast.success("Test Telegram sent");
      } else {
        toast.error("Telegram test failed", res.data.message ?? "Failed to send test message.");
      }
    } catch (err) {
      toast.error("Telegram test failed", err instanceof Error ? err.message : "Failed to send test message.");
    } finally {
      setTelegramLoading(false);
    }
  }

  const signalExportUrl = signalTicker.trim()
    ? `/api/export/signals/csv?ticker=${encodeURIComponent(signalTicker.trim())}`
    : "/api/export/signals/csv";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* -- Email Notifications -- */}
      <Card padding="md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">Email Notifications</h2>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Button size="sm" loading={emailLoading} onClick={handleTestEmail}>
              Send Test Email
            </Button>
          </div>

          <div className="border-t border-gray-800/50 pt-4">
            <h3 className="text-xs font-medium text-gray-400 mb-2">Configuration</h3>
            <p className="text-xs text-gray-500 mb-2">
              Set the following environment variables to enable email notifications:
            </p>
            <div className="rounded-lg bg-gray-950/60 border border-gray-800/40 p-3 font-mono text-xs text-gray-400 space-y-1">
              <div><span className="text-blue-400">SMTP_HOST</span>=smtp.example.com</div>
              <div><span className="text-blue-400">SMTP_PORT</span>=587</div>
              <div><span className="text-blue-400">SMTP_USER</span>=alerts@example.com</div>
              <div><span className="text-blue-400">SMTP_PASS</span>=your-password</div>
              <div><span className="text-blue-400">ALERT_EMAIL_TO</span>=you@example.com</div>
            </div>
          </div>
        </div>
      </Card>

      {/* -- Telegram Notifications -- */}
      <Card padding="md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">Telegram Notifications</h2>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Button size="sm" loading={telegramLoading} onClick={handleTestTelegram}>
              Send Test Telegram
            </Button>
          </div>

          <div className="border-t border-gray-800/50 pt-4">
            <h3 className="text-xs font-medium text-gray-400 mb-2">Configuration</h3>
            <p className="text-xs text-gray-500 mb-2">
              Set the following environment variables to enable Telegram notifications:
            </p>
            <div className="rounded-lg bg-gray-950/60 border border-gray-800/40 p-3 font-mono text-xs text-gray-400 space-y-1">
              <div><span className="text-blue-400">TELEGRAM_BOT_TOKEN</span>=123456:ABC-DEF...</div>
              <div><span className="text-blue-400">TELEGRAM_CHAT_ID</span>=your-chat-id</div>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Create a bot via @BotFather on Telegram. Use /start with the bot and then use the Telegram API to find your chat ID.
            </p>
          </div>
        </div>
      </Card>

      {/* -- Export -- */}
      <Card padding="md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">Export</h2>
        </div>

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
      </Card>
    </div>
  );
}
