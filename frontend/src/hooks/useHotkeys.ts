import { useEffect } from "react";

export function useHotkeys(keyMap: Record<string, () => void>): void {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      const parts: string[] = [];
      if (e.ctrlKey) parts.push("ctrl");
      if (e.metaKey) parts.push("meta");
      if (e.altKey) parts.push("alt");
      if (e.shiftKey) parts.push("shift");
      parts.push(e.key.toLowerCase());

      const combo = parts.join("+");

      for (const [pattern, action] of Object.entries(keyMap)) {
        const normalized = pattern
          .toLowerCase()
          .split("+")
          .sort()
          .join("+");
        const comboSorted = combo
          .split("+")
          .sort()
          .join("+");

        if (normalized === comboSorted) {
          e.preventDefault();
          action();
          return;
        }
      }
    }

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [keyMap]);
}
