import { useTranslation } from "../i18n";

/* ── SVG Icons ── */

function TrendingDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />
      <polyline points="17 18 23 18 23 12" />
    </svg>
  );
}

function ChartDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <path d="M21 9l-6 6-4-4-5 5" />
    </svg>
  );
}

function CpuIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3" />
    </svg>
  );
}

function SlidersIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" y1="21" x2="4" y2="14" />
      <line x1="4" y1="10" x2="4" y2="3" />
      <line x1="12" y1="21" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="20" y1="21" x2="20" y2="16" />
      <line x1="20" y1="12" x2="20" y2="3" />
      <line x1="1" y1="14" x2="7" y2="14" />
      <line x1="9" y1="8" x2="15" y2="8" />
      <line x1="17" y1="16" x2="23" y2="16" />
    </svg>
  );
}

/* ── Highlight helpers ── */

/** Wraps number/percentage patterns in the detail string with colored spans */
function highlightDetail(text: string, color: "emerald" | "blue") {
  const colorClass = color === "emerald" ? "text-emerald-400 font-semibold" : "text-blue-400 font-semibold";
  // Match percentages, percentage-point values, and standalone numbers (e.g. "92%", "-40.7%", "15.4pp", "4")
  const parts = text.split(/(\d+(?:\.\d+)?%?(?:pp)?|-\d+(?:\.\d+)?%?(?:pp)?)/g);
  return parts.map((part, i) =>
    /\d/.test(part) ? (
      <span key={i} className={colorClass}>{part}</span>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

/* ── Card config ── */

interface CardConfig {
  key: "btc" | "spy" | "agents" | "adaptive";
  borderColor: string;
  iconColor: string;
  highlightColor: "emerald" | "blue";
  Icon: React.ComponentType<{ className?: string }>;
}

const cards: CardConfig[] = [
  {
    key: "btc",
    borderColor: "border-emerald-500",
    iconColor: "text-emerald-400",
    highlightColor: "emerald",
    Icon: TrendingDownIcon,
  },
  {
    key: "spy",
    borderColor: "border-emerald-500",
    iconColor: "text-emerald-400",
    highlightColor: "emerald",
    Icon: ChartDownIcon,
  },
  {
    key: "agents",
    borderColor: "border-blue-500",
    iconColor: "text-blue-400",
    highlightColor: "blue",
    Icon: CpuIcon,
  },
  {
    key: "adaptive",
    borderColor: "border-blue-500",
    iconColor: "text-blue-400",
    highlightColor: "blue",
    Icon: SlidersIcon,
  },
];

/* ── Component ── */

export default function Results() {
  const { t } = useTranslation();

  return (
    <section className="relative py-20 bg-gray-950">
      <div className="max-w-5xl mx-auto px-6">
        {/* Section header */}
        <div className="text-center mb-12">
          <span className="inline-block text-[11px] uppercase tracking-widest text-blue-400 font-semibold mb-3">
            {t("results.tag")}
          </span>
          <p className="text-sm text-gray-400">
            {t("hero.highlights.title")}
          </p>
        </div>

        {/* Cards grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {cards.map(({ key, borderColor, iconColor, highlightColor, Icon }) => (
            <div
              key={key}
              className={`rounded-lg border border-gray-800/40 bg-gray-900/40 px-5 py-4 border-l-4 ${borderColor} flex gap-4 items-start`}
            >
              {/* Icon */}
              <div className="shrink-0 mt-0.5">
                <Icon className={`w-5 h-5 ${iconColor}`} />
              </div>

              {/* Text */}
              <div>
                <div className="text-sm font-semibold text-white">
                  {t(`hero.highlights.${key}`)}
                </div>
                <div className="text-[12px] text-gray-500 mt-1 leading-relaxed">
                  {highlightDetail(t(`hero.highlights.${key}.detail`), highlightColor)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
