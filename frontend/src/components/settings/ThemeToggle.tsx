import { useEffect, useState } from "react";
import { Button } from "../ui/Button";

type ThemeOption = "dark" | "light" | "system";

const STORAGE_KEY = "ia_theme";
const OPTIONS: { value: ThemeOption; label: string }[] = [
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
  { value: "system", label: "System" },
];

function readTheme(): ThemeOption {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "dark" || stored === "light" || stored === "system") {
    return stored;
  }
  return "system";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeOption>(readTheme);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return (
    <div className="flex items-center gap-1" role="radiogroup" aria-label="Theme selection">
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
