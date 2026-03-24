import { type ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: "none" | "sm" | "md" | "lg";
}

interface CardHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
}

interface CardBodyProps {
  children: ReactNode;
  className?: string;
}

const paddingStyles: Record<NonNullable<CardProps["padding"]>, string> = {
  none: "p-0",
  sm: "p-3 sm:p-4",
  md: "p-4 sm:p-5",
  lg: "p-5 sm:p-6",
};

export const Card = ({
  children,
  className = "",
  padding = "none",
}: CardProps) => (
  <div
    className={`
      rounded-card bg-gray-900 border border-gray-800/60 shadow-card
      ${paddingStyles[padding]}
      ${className}
    `}
  >
    {children}
  </div>
);

export const CardHeader = ({
  title,
  subtitle,
  action,
  className = "",
}: CardHeaderProps) => (
  <div
    className={`px-4 sm:px-5 py-3.5 border-b border-gray-800/40 flex items-center justify-between ${className}`}
  >
    <div>
      <h3 className="text-sm font-semibold text-gray-200">{title}</h3>
      {subtitle && (
        <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>
      )}
    </div>
    {action && <div>{action}</div>}
  </div>
);

export const CardBody = ({ children, className = "" }: CardBodyProps) => (
  <div className={`p-4 sm:p-5 ${className}`}>{children}</div>
);
