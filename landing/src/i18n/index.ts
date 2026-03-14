import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import React from "react";
import en from "./en.json";
import zh from "./zh.json";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export type Language = "en" | "zh";

type Translations = Record<string, string>;

const translations: Record<Language, Translations> = { en, zh };

interface I18nContextValue {
  lang: Language;
  setLang: (l: Language) => void;
  t: (key: string) => string;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
const I18nContext = createContext<I18nContextValue | null>(null);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function getInitialLang(): Language {
  // 1. URL ?lang=
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("lang");
  if (fromUrl === "zh" || fromUrl === "en") return fromUrl;

  // 2. localStorage
  const stored = localStorage.getItem("lang");
  if (stored === "zh" || stored === "en") return stored as Language;

  // 3. default
  return "en";
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>(getInitialLang);

  const setLang = useCallback((l: Language) => {
    setLangState(l);
    localStorage.setItem("lang", l);
    // update URL without reload
    const url = new URL(window.location.href);
    if (l === "en") {
      url.searchParams.delete("lang");
    } else {
      url.searchParams.set("lang", l);
    }
    window.history.replaceState(null, "", url.toString());
  }, []);

  // sync <html lang> and document title
  useEffect(() => {
    document.documentElement.lang = lang;
    document.title =
      lang === "zh"
        ? "未来投资引擎 — 不只记录，更帮你把关"
        : "Investment Agent — The Investment Journal That Fights Back";
  }, [lang]);

  const t = useCallback(
    (key: string): string => {
      return translations[lang]?.[key] ?? translations.en?.[key] ?? key;
    },
    [lang],
  );

  return React.createElement(
    I18nContext.Provider,
    { value: { lang, setLang, t } },
    children,
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------
export function useTranslation() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useTranslation must be used inside LanguageProvider");
  return ctx;
}
