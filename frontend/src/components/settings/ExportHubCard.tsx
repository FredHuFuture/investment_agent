import { useState } from "react";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { TextInput } from "../ui/Input";

interface ExportLink {
  label: string;
  href: string;
}

interface ExportCategory {
  name: string;
  links: ExportLink[];
}

const EXPORT_CATEGORIES: ExportCategory[] = [
  {
    name: "Portfolio",
    links: [
      { label: "Portfolio CSV", href: "/api/export/portfolio/csv" },
      { label: "Trade Journal CSV", href: "/api/export/trades/csv" },
      { label: "Full Report", href: "/api/export/portfolio/report" },
    ],
  },
  {
    name: "Performance",
    links: [
      { label: "Performance CSV", href: "/api/export/performance/csv" },
    ],
  },
  {
    name: "Risk",
    links: [
      { label: "Risk CSV", href: "/api/export/risk/csv" },
    ],
  },
  {
    name: "Signals",
    links: [
      { label: "All Signals CSV", href: "/api/export/signals/csv" },
    ],
  },
  {
    name: "Alerts",
    links: [
      { label: "Alerts CSV", href: "/api/export/alerts/csv" },
    ],
  },
];

const linkClassName =
  "px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-xs font-medium text-gray-300 transition-colors inline-block";

export default function ExportHubCard() {
  const [signalTicker, setSignalTicker] = useState("");

  const signalExportUrl = signalTicker.trim()
    ? `/api/export/signals/csv?ticker=${encodeURIComponent(signalTicker.trim())}`
    : "/api/export/signals/csv";

  return (
    <Card>
      <CardHeader title="Export Hub" subtitle="Download your data by category" />
      <CardBody>
        <div className="space-y-4">
          {EXPORT_CATEGORIES.map((category) => (
            <div key={category.name}>
              <h3 className="text-xs font-medium text-gray-400 mb-2">
                {category.name}
              </h3>
              <div className="flex flex-wrap gap-2">
                {category.links.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    download
                    className={linkClassName}
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            </div>
          ))}

          <div className="border-t border-gray-800/50 pt-4">
            <h3 className="text-xs font-medium text-gray-400 mb-2">
              Signal History Export
            </h3>
            <div className="flex items-center gap-2">
              <TextInput
                value={signalTicker}
                onChange={(e) => setSignalTicker(e.target.value.toUpperCase())}
                placeholder="Filter by ticker"
                className="w-52"
              />
              <a
                href={signalExportUrl}
                download
                className={linkClassName}
              >
                Download Signals
              </a>
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
