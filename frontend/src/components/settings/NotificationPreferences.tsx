import { useEffect, useState } from "react";
import { Button } from "../ui/Button";
import { testEmailNotification, testTelegramNotification } from "../../api/endpoints";
import { useToast } from "../../contexts/ToastContext";

const EMAIL_KEY = "ia_notify_email";
const TELEGRAM_KEY = "ia_notify_telegram";

function readBool(key: string): boolean {
  return localStorage.getItem(key) === "true";
}

export default function NotificationPreferences() {
  const { toast } = useToast();
  const [emailEnabled, setEmailEnabled] = useState(() => readBool(EMAIL_KEY));
  const [telegramEnabled, setTelegramEnabled] = useState(() => readBool(TELEGRAM_KEY));
  const [emailLoading, setEmailLoading] = useState(false);
  const [telegramLoading, setTelegramLoading] = useState(false);

  useEffect(() => {
    localStorage.setItem(EMAIL_KEY, String(emailEnabled));
  }, [emailEnabled]);

  useEffect(() => {
    localStorage.setItem(TELEGRAM_KEY, String(telegramEnabled));
  }, [telegramEnabled]);

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

  return (
    <div className="space-y-4">
      {/* Email row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-300">Email</span>
          <Button
            size="sm"
            variant={emailEnabled ? "primary" : "ghost"}
            onClick={() => setEmailEnabled((v) => !v)}
            aria-pressed={emailEnabled}
          >
            {emailEnabled ? "On" : "Off"}
          </Button>
        </div>
        <Button size="sm" variant="secondary" loading={emailLoading} onClick={handleTestEmail}>
          Send Test Email
        </Button>
      </div>

      {/* Telegram row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-300">Telegram</span>
          <Button
            size="sm"
            variant={telegramEnabled ? "primary" : "ghost"}
            onClick={() => setTelegramEnabled((v) => !v)}
            aria-pressed={telegramEnabled}
          >
            {telegramEnabled ? "On" : "Off"}
          </Button>
        </div>
        <Button size="sm" variant="secondary" loading={telegramLoading} onClick={handleTestTelegram}>
          Send Test Telegram
        </Button>
      </div>

      {/* Configuration hints */}
      <div className="border-t border-gray-800/50 pt-4">
        <h3 className="text-xs font-medium text-gray-400 mb-2">Configuration</h3>
        <p className="text-xs text-gray-500 mb-2">
          Set the following environment variables to enable notifications:
        </p>
        <div className="rounded-lg bg-gray-950/60 border border-gray-800/40 p-3 font-mono text-xs text-gray-400 space-y-1">
          <div><span className="text-blue-400">SMTP_HOST</span>=smtp.example.com</div>
          <div><span className="text-blue-400">SMTP_PORT</span>=587</div>
          <div><span className="text-blue-400">SMTP_USER</span>=alerts@example.com</div>
          <div><span className="text-blue-400">SMTP_PASS</span>=your-password</div>
          <div><span className="text-blue-400">ALERT_EMAIL_TO</span>=you@example.com</div>
          <div className="mt-2"><span className="text-blue-400">TELEGRAM_BOT_TOKEN</span>=123456:ABC-DEF...</div>
          <div><span className="text-blue-400">TELEGRAM_CHAT_ID</span>=your-chat-id</div>
        </div>
      </div>
    </div>
  );
}
