import { useTranslation } from "../i18n";

const GITHUB_URL = "https://github.com/FredHuFuture/investment_agent";

export default function Hero() {
  const { t } = useTranslation();

  const stats = [
    { value: t("hero.stats.agents.value"), label: t("hero.stats.agents.label") },
    { value: t("hero.stats.tests.value"), label: t("hero.stats.tests.label") },
    { value: t("hero.stats.endpoints.value"), label: t("hero.stats.endpoints.label") },
    { value: t("hero.stats.backtest.value"), label: t("hero.stats.backtest.label") },
  ];

  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* ── Mesh gradient background ── */}
      <div className="absolute inset-0 bg-gradient-to-b from-gray-950 via-gray-950 to-gray-950">
        {/* Blue blob — top right */}
        <div
          className="mesh-blob"
          style={{
            width: 600,
            height: 600,
            top: "-10%",
            right: "-5%",
            background:
              "radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%)",
            animationDelay: "0s",
          }}
        />
        {/* Purple blob — center left */}
        <div
          className="mesh-blob"
          style={{
            width: 500,
            height: 500,
            top: "30%",
            left: "-8%",
            background:
              "radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%)",
            animationDelay: "-7s",
          }}
        />
        {/* Teal accent — bottom */}
        <div
          className="mesh-blob"
          style={{
            width: 400,
            height: 400,
            bottom: "5%",
            right: "20%",
            background:
              "radial-gradient(circle, rgba(6,182,212,0.06) 0%, transparent 70%)",
            animationDelay: "-13s",
          }}
        />
      </div>

      {/* ── Subtle grid overlay ── */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* ── Content ── */}
      <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-600/20">
            <svg
              className="w-8 h-8 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
        </div>

        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-gray-800/60 bg-gray-900/50 text-xs text-gray-400 mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          {t("hero.badge")}
        </div>

        {/* Title */}
        <h1 className="text-5xl sm:text-6xl md:text-7xl font-extrabold tracking-tight leading-[1.08] mb-6">
          <span className="text-white">{t("hero.title.line1")}</span>
          <br />
          <span className="bg-gradient-to-r from-blue-400 via-blue-300 to-cyan-300 bg-clip-text text-transparent">
            {t("hero.title.line2")}
          </span>
        </h1>

        {/* Subtitle */}
        <p className="text-lg sm:text-xl text-gray-400 max-w-2xl mx-auto leading-relaxed mb-10">
          {t("hero.subtitle")}
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-2.5 px-7 py-3.5 bg-white text-gray-900 rounded-xl font-semibold text-sm hover:bg-gray-100 transition-colors shadow-lg shadow-white/5"
          >
            <svg
              className="w-5 h-5"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
            </svg>
            {t("hero.cta.github")}
          </a>
          <a
            href="#demo"
            className="inline-flex items-center gap-2 px-7 py-3.5 rounded-xl font-semibold text-sm text-gray-300 border border-gray-700/60 hover:border-gray-600 hover:text-white transition-colors bg-gray-900/30"
          >
            {t("hero.cta.demo")}
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M6 9l6 6 6-6" />
            </svg>
          </a>
        </div>

        {/* Credibility bar */}
        <div className="mt-12 inline-flex items-center gap-3 px-5 py-2.5 rounded-full border border-gray-800/40 bg-gray-900/30">
          <svg className="w-4 h-4 text-blue-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          <span className="text-xs sm:text-sm text-gray-400">
            {t("hero.credibility")}<span className="text-gray-300 font-medium">{t("hero.credibility.highlight")}</span>
          </span>
        </div>

        {/* Stats row */}
        <div className="mt-10 flex items-center justify-center gap-10 sm:gap-16 text-center">
          {stats.map((s) => (
            <div key={s.label}>
              <div className="text-2xl font-bold text-white">{s.value}</div>
              <div className="text-xs text-gray-500 mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

      </div>

      {/* ── Scroll indicator ── */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
        <svg
          className="w-5 h-5 text-gray-600"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>
    </section>
  );
}
