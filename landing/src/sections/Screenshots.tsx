import { useTranslation } from "../i18n";

// ---------------------------------------------------------------------------
// Browser-frame wrapper for GIF screenshots
// ---------------------------------------------------------------------------
function BrowserFrame({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="browser-frame group">
      {/* Title bar */}
      <div className="browser-frame-bar">
        <span className="browser-dot bg-[#ff5f57]" />
        <span className="browser-dot bg-[#febc2e]" />
        <span className="browser-dot bg-[#28c840]" />
        <span className="ml-3 text-[11px] text-gray-500 font-mono truncate">
          {title}
        </span>
      </div>
      {/* Content area */}
      <div className="aspect-video bg-gray-950 flex items-center justify-center overflow-hidden">
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Screenshot data (keys reference i18n)
// ---------------------------------------------------------------------------
const demos = [
  {
    gif: "gifs/analysis-demo.gif",
    title: "localhost:5173/analyze",
    labelKey: "screenshots.analysis.label",
    captionKey: "screenshots.analysis.caption",
  },
  {
    gif: "gifs/backtest-demo.gif",
    title: "localhost:5173/backtest",
    labelKey: "screenshots.backtest.label",
    captionKey: "screenshots.backtest.caption",
  },
  {
    gif: "gifs/dashboard-demo.gif",
    title: "localhost:5173/",
    labelKey: "screenshots.dashboard.label",
    captionKey: "screenshots.dashboard.caption",
  },
  {
    gif: "gifs/monitoring-demo.gif",
    title: "localhost:5173/monitoring",
    labelKey: "screenshots.monitoring.label",
    captionKey: "screenshots.monitoring.caption",
  },
];

export default function Screenshots() {
  const { t } = useTranslation();

  return (
    <section id="demo" className="relative py-24 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Section header */}
        <div className="text-center mb-16">
          <p className="text-xs uppercase tracking-widest text-blue-400 font-semibold mb-3">
            {t("screenshots.tag")}
          </p>
          <h2 className="text-3xl sm:text-4xl font-bold text-white">
            {t("screenshots.title")}
          </h2>
          <p className="mt-4 text-gray-400 max-w-xl mx-auto">
            {t("screenshots.subtitle")}
          </p>
        </div>

        {/* Grid of screenshots */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {demos.map((d) => (
            <div key={d.labelKey} className="space-y-3">
              <BrowserFrame title={d.title}>
                {/* Try to load GIF; show placeholder if not found */}
                <img
                  src={d.gif}
                  alt={t(d.labelKey)}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    // Hide broken image, show placeholder
                    const target = e.currentTarget;
                    target.style.display = "none";
                    const parent = target.parentElement;
                    if (parent) {
                      const ph = document.createElement("div");
                      ph.className =
                        "w-full h-full flex flex-col items-center justify-center gap-3 text-gray-600";
                      ph.innerHTML = `
                        <svg class="w-10 h-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                          <rect x="2" y="2" width="20" height="20" rx="2"/>
                          <path d="M7 2v20M17 2v20M2 7h20M2 12h20M2 17h20"/>
                        </svg>
                        <span class="text-xs">GIF recording pending</span>
                      `;
                      parent.appendChild(ph);
                    }
                  }}
                />
              </BrowserFrame>
              <div>
                <h3 className="text-sm font-semibold text-white">
                  {t(d.labelKey)}
                </h3>
                <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
                  {t(d.captionKey)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
