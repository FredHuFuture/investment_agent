export default function EmptyState({
  message,
  hint,
}: {
  message: string;
  hint?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4">
      <div className="w-14 h-14 rounded-2xl bg-gray-800/40 border border-gray-800/40 flex items-center justify-center">
        <svg
          className="w-7 h-7 text-gray-600"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M3 3v18h18" />
          <path d="M7 16l4-5 4 3 5-6" />
        </svg>
      </div>
      <div className="text-center">
        <p className="text-sm text-gray-400">{message}</p>
        {hint && <p className="text-xs text-gray-600 mt-1">{hint}</p>}
      </div>
    </div>
  );
}
