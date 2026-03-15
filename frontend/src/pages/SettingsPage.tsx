import { useState } from "react";
import { testEmailNotification, testTelegramNotification } from "../api/endpoints";

type TestStatus = "idle" | "loading" | "success" | "error";

interface TestResult {
  status: TestStatus;
  message: string;
}

export default function SettingsPage() {
  const [emailTest, setEmailTest] = useState<TestResult>({ status: "idle", message: "" });
  const [telegramTest, setTelegramTest] = useState<TestResult>({ status: "idle", message: "" });
  const [signalTicker, setSignalTicker] = useState("");

  async function handleTestEmail() {
    setEmailTest({ status: "loading", message: "Sending test email..." });
    try {
      const res = await testEmailNotification();
      if (res.data.sent) {
        setEmailTest({ status: "success", message: "Test email sent successfully." });
      } else {
        setEmailTest({ status: "error", message: res.data.message ?? "Failed to send test email." });
      }
    } catch (err) {
      setEmailTest({
        status: "error",
        message: err instanceof Error ? err.message : "Failed to send test email.",
      });
    }
  }

  async function handleTestTelegram() {
    setTelegramTest({ status: "loading", message: "Sending test message..." });
    try {
      const res = await testTelegramNotification();
      if (res.data.sent) {
        setTelegramTest({ status: "success", message: "Test Telegram message sent successfully." });
      } else {
        setTelegramTest({ status: "error", message: res.data.message ?? "Failed to send test message." });
      }
    } catch (err) {
      setTelegramTest({
        status: "error",
        message: err instanceof Error ? err.message : "Failed to send test message.",
      });
    }
  }

  const signalExportUrl = signalTicker.trim()
    ? `/api/export/signals/csv?ticker=${encodeURIComponent(signalTicker.trim())}`
    : "/api/export/signals/csv";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* ── Email Notifications ── */}
      <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">Email Notifications</h2>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              onClick={handleTestEmail}
              disabled={emailTest.status === "loading"}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-xs font-medium text-white transition-colors"
            >
              {emailTest.status === "loading" ? "Sending..." : "Send Test Email"}
            </button>
            {emailTest.status === "success" && (
              <span className="text-xs text-emerald-400">{emailTest.message}</span>
            )}
            {emailTest.status === "error" && (
              <span className="text-xs text-red-400">{emailTest.message}</span>
            )}
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
      </div>

      {/* ── Telegram Notifications ── */}
      <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">Telegram Notifications</h2>
        </div>

        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              onClick={handleTestTelegram}
              disabled={telegramTest.status === "loading"}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-xs font-medium text-white transition-colors"
            >
              {telegramTest.status === "loading" ? "Sending..." : "Send Test Telegram"}
            </button>
            {telegramTest.status === "success" && (
              <span className="text-xs text-emerald-400">{telegramTest.message}</span>
            )}
            {telegramTest.status === "error" && (
              <span className="text-xs text-red-400">{telegramTest.message}</span>
            )}
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
      </div>

      {/* ── Export ── */}
      <div className="rounded-xl bg-gray-900/50 backdrop-blur border border-gray-800/50 p-5">
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
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium text-gray-300 transition-colors"
              >
                Portfolio CSV
              </a>
              <a
                href="/api/export/trades/csv"
                download
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium text-gray-300 transition-colors"
              >
                Trade Journal CSV
              </a>
              <a
                href="/api/export/portfolio/report"
                download
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium text-gray-300 transition-colors"
              >
                Full Report
              </a>
              <a
                href="/api/export/signals/csv"
                download
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium text-gray-300 transition-colors"
              >
                All Signals CSV
              </a>
            </div>
          </div>

          <div className="border-t border-gray-800/50 pt-4">
            <h3 className="text-xs font-medium text-gray-400 mb-3">Signal History Export</h3>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={signalTicker}
                onChange={(e) => setSignalTicker(e.target.value.toUpperCase())}
                placeholder="Filter by ticker (optional)"
                className="px-3 py-1.5 bg-gray-950/60 border border-gray-800/40 rounded-lg text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500/50 w-52"
              />
              <a
                href={signalExportUrl}
                download
                className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-xs font-medium text-gray-300 transition-colors"
              >
                Download Signals
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
