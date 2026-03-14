import { useTranslation, type Language } from "../i18n";

const options: { value: Language; label: string }[] = [
  { value: "en", label: "EN" },
  { value: "zh", label: "中文" },
];

export default function LanguageSwitcher() {
  const { lang, setLang } = useTranslation();

  return (
    <div className="fixed top-6 right-6 z-50 flex rounded-full bg-gray-950/90 backdrop-blur-md border border-gray-700/60 p-0.5 shadow-xl">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => setLang(o.value)}
          className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors ${
            lang === o.value
              ? "bg-gray-800 text-white shadow-sm"
              : "text-gray-500 hover:text-gray-300"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
