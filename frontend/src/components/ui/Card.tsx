import { type ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: "none" | "sm" | "md" | "lg";
}

interface CardHeaderProps {
  title: string;
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
      bg-gray-900 border border-gray-800 rounded-xl
      ${paddingStyles[padding]}
      ${className}
    `}
  >
    {children}
  </div>
);

export const CardHeader = ({ title, action, className = "" }: CardHeaderProps) => (
  <div
    className={`px-5 py-4 border-b border-gray-800 flex items-center justify-between ${className}`}
  >
    <h3 className="text-lg font-semibold text-gray-100">{title}</h3>
    {action && <div>{action}</div>}
  </div>
);

export const CardBody = ({ children, className = "" }: CardBodyProps) => (
  <div className={`p-5 ${className}`}>{children}</div>
);
