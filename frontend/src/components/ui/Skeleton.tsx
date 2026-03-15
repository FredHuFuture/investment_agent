import { type CSSProperties } from "react";

interface SkeletonProps {
  variant?: "text" | "rectangular" | "circular";
  width?: string | number;
  height?: string | number;
  lines?: number;
  className?: string;
}

const LINE_WIDTHS = ["w-full", "w-[85%]", "w-[70%]", "w-[90%]", "w-[60%]", "w-[95%]", "w-[75%]", "w-[80%]"];

const getLineWidth = (index: number): string =>
  LINE_WIDTHS[index % LINE_WIDTHS.length] ?? "w-full";

export const Skeleton = ({
  variant = "text",
  width,
  height,
  lines = 1,
  className = "",
}: SkeletonProps) => {
  const dynamicStyle: CSSProperties = {
    ...(width != null ? { width: typeof width === "number" ? `${width}px` : width } : {}),
    ...(height != null ? { height: typeof height === "number" ? `${height}px` : height } : {}),
  };

  if (variant === "circular") {
    const size = width ?? height ?? 40;
    const circleStyle: CSSProperties = {
      width: typeof size === "number" ? `${size}px` : size,
      height: typeof size === "number" ? `${size}px` : size,
    };
    return (
      <div
        className={`animate-pulse bg-gray-800 rounded-full ${className}`}
        style={circleStyle}
      />
    );
  }

  if (variant === "rectangular") {
    return (
      <div
        className={`animate-pulse bg-gray-800 rounded-lg ${className}`}
        style={dynamicStyle}
      />
    );
  }

  // text variant
  if (lines > 1) {
    return (
      <div className={`flex flex-col gap-2 ${className}`}>
        {Array.from({ length: lines }, (_, i) => (
          <div
            key={i}
            className={`animate-pulse bg-gray-800 rounded h-4 ${getLineWidth(i)}`}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`animate-pulse bg-gray-800 rounded h-4 w-full ${className}`}
      style={dynamicStyle}
    />
  );
};

export const SkeletonCard = ({ className = "" }: { className?: string }) => (
  <div className={`bg-gray-900 border border-gray-800 rounded-xl p-5 ${className}`}>
    <Skeleton variant="text" width="40%" className="mb-3" />
    <Skeleton variant="rectangular" height={20} className="mb-4" />
    <Skeleton variant="text" lines={3} />
  </div>
);

export const SkeletonTable = ({
  rows = 5,
  columns = 4,
  className = "",
}: {
  rows?: number;
  columns?: number;
  className?: string;
}) => (
  <div className={`bg-gray-900 border border-gray-800 rounded-xl overflow-hidden ${className}`}>
    {/* Header */}
    <div className="flex gap-4 px-5 py-3 border-b border-gray-800">
      {Array.from({ length: columns }, (_, i) => (
        <Skeleton key={i} variant="text" height={14} className="flex-1" />
      ))}
    </div>
    {/* Rows */}
    {Array.from({ length: rows }, (_, rowIdx) => (
      <div
        key={rowIdx}
        className="flex gap-4 px-5 py-3 border-b border-gray-800/50 last:border-b-0"
      >
        {Array.from({ length: columns }, (_, colIdx) => (
          <Skeleton key={colIdx} variant="text" height={14} className="flex-1" />
        ))}
      </div>
    ))}
  </div>
);
