import { useTranslation } from "../i18n";

const featureKeys = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
        <circle cx="12" cy="12" r="10" />
        <path d="M8 12h8M12 8v8" />
      </svg>
    ),
    color: "blue",
    titleKey: "features.multiAgent.title",
    descKey: "features.multiAgent.desc",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
      </svg>
    ),
    color: "emerald",
    titleKey: "features.thesis.title",
    descKey: "features.thesis.desc",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
    ),
    color: "amber",
    titleKey: "features.monitoring.title",
    descKey: "features.monitoring.desc",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
        <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
        <path d="M3 3v5h5" />
        <path d="M12 7v5l4 2" />
      </svg>
    ),
    color: "violet",
    titleKey: "features.backtest.title",
    descKey: "features.backtest.desc",
  },
];

const colorMap: Record<string, { bg: string; text: string; glow: string; ring: string }> = {
  blue: {
    bg: "bg-blue-500/10",
    text: "text-blue-400",
    glow: "group-hover:shadow-blue-500/10",
    ring: "ring-1 ring-blue-500/20",
  },
  emerald: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    glow: "group-hover:shadow-emerald-500/10",
    ring: "ring-1 ring-emerald-500/20",
  },
  amber: {
    bg: "bg-amber-500/10",
    text: "text-amber-400",
    glow: "group-hover:shadow-amber-500/10",
    ring: "ring-1 ring-amber-500/20",
  },
  violet: {
    bg: "bg-violet-500/10",
    text: "text-violet-400",
    glow: "group-hover:shadow-violet-500/10",
    ring: "ring-1 ring-violet-500/20",
  },
};

export default function Features() {
  const { t } = useTranslation();

  return (
    <section className="relative py-24 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16">
          <p className="text-xs uppercase tracking-widest text-blue-400 font-semibold mb-3">
            {t("features.tag")}
          </p>
          <h2 className="text-3xl sm:text-4xl font-bold text-white">
            {t("features.title")}
          </h2>
          <p className="mt-4 text-gray-400 max-w-xl mx-auto">
            {t("features.subtitle")}
          </p>
        </div>

        {/* Cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {featureKeys.map((f) => {
            const c = colorMap[f.color] ?? colorMap.blue!;
            return (
              <div
                key={f.titleKey}
                className={`group feature-card rounded-2xl bg-gray-900/50 border border-gray-800/50 p-7 backdrop-blur-sm transition-shadow ${c.glow}`}
              >
                <div
                  className={`w-14 h-14 rounded-xl ${c.bg} ${c.text} ${c.ring} flex items-center justify-center mb-5`}
                >
                  {f.icon}
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">
                  {t(f.titleKey)}
                </h3>
                <p className="text-sm text-gray-400 leading-relaxed">
                  {t(f.descKey)}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
