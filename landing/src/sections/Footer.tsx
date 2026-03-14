import { useTranslation } from "../i18n";

const GITHUB_URL = "https://github.com/FredHuFuture/investment_agent";

export default function Footer() {
  const { t } = useTranslation();

  return (
    <footer className="relative py-16 px-6">
      <div className="max-w-5xl mx-auto flex flex-col items-center gap-5">
        {/* Logo + name + version */}
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center">
            <svg
              className="w-3.5 h-3.5 text-white"
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
          <span className="text-sm font-semibold text-gray-400">
            {t("footer.name")}
          </span>
          <span className="text-xs text-gray-600">{t("footer.version")}</span>
        </div>

        {/* Tagline */}
        <p className="text-sm text-gray-500 italic">
          {t("footer.tagline")}
        </p>

        {/* GitHub stars badge */}
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
        >
          <img
            src="https://img.shields.io/github/stars/peterryang/investment-agent?style=social"
            alt="GitHub stars"
            className="h-5"
          />
        </a>

        {/* Links */}
        <div className="flex items-center gap-6 text-xs text-gray-500">
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-300 transition-colors"
          >
            {t("footer.links.github")}
          </a>
          <a
            href={`${GITHUB_URL}/blob/main/LICENSE`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-300 transition-colors"
          >
            {t("footer.links.license")}
          </a>
          <a
            href={`${GITHUB_URL}/blob/main/docs/architecture_v5.md`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-300 transition-colors"
          >
            {t("footer.links.arch")}
          </a>
        </div>

        {/* Copyright */}
        <div className="text-[11px] text-gray-600">
          &copy; 2026
        </div>
      </div>
    </footer>
  );
}
