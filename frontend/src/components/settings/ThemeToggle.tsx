import { useEffect, useState } from "react";
import { Button } from "../ui/Button";

type ThemeOption = "dark" | "light" | "system";

const STORAGE_KEY = "ia_theme";

function getSystemTheme(): "dark" | "light" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function readTheme(): ThemeOption {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "dark" || stored === "light" || stored === "system") {
    return stored;
  }
  return "dark";
}

function applyTheme(theme: ThemeOption) {
  const resolved = theme === "system" ? getSystemTheme() : theme;
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

const OPTIONS: { value: ThemeOption; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

export default function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeOption>(readTheme);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, theme);
    applyTheme(theme);
  }, [theme]);

  // Listen for system theme changes when "system" is selected
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyTheme("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  return (
    <div
      className="flex items-center gap-1"
      role="radiogroup"
      aria-label="Theme selection"
    >
      {OPTIONS.map((opt) => (
        <Button
          key={opt.value}
          size="sm"
          variant={theme === opt.value ? "primary" : "ghost"}
          onClick={() => setTheme(opt.value)}
          aria-checked={theme === opt.value}
          role="radio"
        >
          {opt.label}
        </Button>
      ))}
    </div>
  );
}
