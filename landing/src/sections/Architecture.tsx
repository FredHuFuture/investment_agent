import type { ReactNode } from "react";
import { useTranslation } from "../i18n";

// ---------------------------------------------------------------------------
// Pipeline flow diagram (pure CSS/HTML)
// ---------------------------------------------------------------------------
function FlowStep({
  icon,
  label,
  sub,
  color,
}: {
  icon: ReactNode;
  label: string;
  sub: string;
  color: string;
}) {
  return (
    <div className="flex flex-col items-center text-center">
      <div
        className={`w-14 h-14 rounded-xl ${color} flex items-center justify-center mb-2`}
      >
        {icon}
      </div>
      <div className="text-sm font-semibold text-white">{label}</div>
      <div className="text-[10px] text-gray-500 mt-0.5 max-w-[120px]">
        {sub}
      </div>
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex items-center">
      <div className="w-8 sm:w-12 h-px bg-gray-700" />
      <svg
        className="w-3 h-3 text-gray-600 -ml-1"
        viewBox="0 0 24 24"
        fill="currentColor"
      >
        <path d="M8 4l8 8-8 8z" />
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tech stack badges
// ---------------------------------------------------------------------------
const PILL_COLOR = "bg-gray-800/50 text-gray-300 border-gray-700/50";

const techStack = [
  { name: "Python 3.11+", color: PILL_COLOR },
  { name: "FastAPI", color: PILL_COLOR },
  { name: "React 18", color: PILL_COLOR },
  { name: "TypeScript", color: PILL_COLOR },
  { name: "SQLite + WAL", color: PILL_COLOR },
  { name: "Tailwind CSS", color: PILL_COLOR },
  { name: "Plotly", color: PILL_COLOR },
  { name: "yfinance", color: PILL_COLOR },
  { name: "Recharts", color: PILL_COLOR },
];

export default function Architecture() {
  const { t } = useTranslation();

  const flowSteps: { labelKey: string; subKey: string; color: string; icon: ReactNode }[] = [
    {
      labelKey: "arch.flow.data", subKey: "arch.flow.data.sub", color: "bg-emerald-500/15 text-emerald-400",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
          <ellipse cx="12" cy="5" rx="9" ry="3" />
          <path d="M21 12c0 1.66-4.03 3-9 3s-9-1.34-9-3" />
          <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
        </svg>
      ),
    },
    {
      labelKey: "arch.flow.agents", subKey: "arch.flow.agents.sub", color: "bg-blue-500/15 text-blue-400",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
          <rect x="4" y="4" width="16" height="16" rx="2" />
          <rect x="9" y="9" width="6" height="6" rx="1" />
          <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 15h3M1 9h3M1 15h3" />
        </svg>
      ),
    },
    {
      labelKey: "arch.flow.aggregator", subKey: "arch.flow.aggregator.sub", color: "bg-violet-500/15 text-violet-400",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
          <path d="M18 8c0 4-6 8-6 12M6 8c0 4 6 8 6 12" />
          <circle cx="18" cy="5" r="3" />
          <circle cx="6" cy="5" r="3" />
          <circle cx="12" cy="20" r="2" />
        </svg>
      ),
    },
    {
      labelKey: "arch.flow.signals", subKey: "arch.flow.signals.sub", color: "bg-amber-500/15 text-amber-400",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
        </svg>
      ),
    },
    {
      labelKey: "arch.flow.monitor", subKey: "arch.flow.monitor.sub", color: "bg-rose-500/15 text-rose-400",
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-7 h-7">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
      ),
    },
  ];

  const differentiators = [
    {
      titleKey: "arch.diff.selfHosted.title",
      descKey: "arch.diff.selfHosted.desc",
      icon: "M12 22s-8-4.5-8-11.8A8 8 0 0 1 12 2a8 8 0 0 1 8 8.2C20 17.5 12 22 12 22z",
    },
    {
      titleKey: "arch.diff.ruleBased.title",
      descKey: "arch.diff.ruleBased.desc",
      icon: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
    },
    {
      titleKey: "arch.diff.thesis.title",
      descKey: "arch.diff.thesis.desc",
      icon: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
    },
  ];

  return (
    <section className="relative py-24 px-6">
      <div className="max-w-5xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16">
          <p className="text-xs uppercase tracking-widest text-blue-400 font-semibold mb-3">
            {t("arch.tag")}
          </p>
          <h2 className="text-3xl sm:text-4xl font-bold text-white">
            {t("arch.title")}
          </h2>
          <p className="mt-4 text-gray-400 max-w-xl mx-auto">
            {t("arch.subtitle")}
          </p>
        </div>

        {/* Flow diagram */}
        <div className="flex flex-wrap items-center justify-center gap-y-6 mb-20">
          {flowSteps.map((step, i) => (
            <span key={step.labelKey} className="contents">
              <FlowStep
                icon={step.icon}
                label={t(step.labelKey)}
                sub={t(step.subKey)}
                color={step.color}
              />
              {i < flowSteps.length - 1 && <Arrow />}
            </span>
          ))}
        </div>

        {/* Key differentiators */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-20">
          {differentiators.map((item) => (
            <div
              key={item.titleKey}
              className="rounded-xl bg-gray-900/40 border border-gray-800/40 p-5"
            >
              <svg
                className="w-5 h-5 text-gray-500 mb-3"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d={item.icon} />
              </svg>
              <h4 className="text-sm font-semibold text-white mb-1">
                {t(item.titleKey)}
              </h4>
              <p className="text-xs text-gray-500 leading-relaxed">
                {t(item.descKey)}
              </p>
            </div>
          ))}
        </div>

        {/* Tech stack badges */}
        <div className="text-center">
          <p className="text-xs uppercase tracking-widest text-gray-500 font-semibold mb-4">
            {t("arch.techStack")}
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {techStack.map((tech) => (
              <span
                key={tech.name}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${tech.color}`}
              >
                {tech.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
