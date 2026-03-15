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
  sm: "p-3",
  md: "p-5",
  lg: "p-6",
};

export const Card = ({
  children,
  className = "",
  padding = "none",
}: CardProps) => (
  <div
    className={`
      rounded-xl bg-gray-900/50 backdrop-blur-sm border border-gray-800/50
      ${paddingStyles[padding]}
      ${className}
    `}
  >
    {children}
  </div>
);

export const CardHeader = ({ title, subtitle, action, className = "" }: CardHeaderProps) => (
  <div
    className={`px-5 py-4 border-b border-gray-800/50 flex items-center justify-between ${className}`}
  >
    <div>
      <h3 className="text-sm font-semibold text-gray-300">{title}</h3>
      {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
    </div>
    {action && <div>{action}</div>}
  </div>
);

export const CardBody = ({ children, className = "" }: CardBodyProps) => (
  <div className={`p-5 ${className}`}>{children}</div>
);
