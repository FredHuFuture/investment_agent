import { Link } from "react-router-dom";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbProps {
  items: BreadcrumbItem[];
}

function HomeIcon() {
  return (
    <svg
      className="w-4 h-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z" />
      <path d="M9 22V12h6v10" />
    </svg>
  );
}

export default function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav className="flex items-center gap-2 text-sm" aria-label="Breadcrumb">
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <span key={i} className="flex items-center gap-2">
            {i > 0 && <span className="text-gray-600">›</span>}
            {isLast || !item.href ? (
              <span className="text-gray-200 font-medium flex items-center gap-1.5">
                {item.label === "Home" && <HomeIcon />}
                {item.label}
              </span>
            ) : (
              <Link
                to={item.href}
                className="text-gray-400 hover:text-gray-200 transition-colors flex items-center gap-1.5"
              >
                {item.label === "Home" && <HomeIcon />}
                {item.label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
