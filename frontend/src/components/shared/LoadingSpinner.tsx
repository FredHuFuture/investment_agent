export default function LoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-700 border-t-accent" />
      <span className="text-xs text-gray-500 animate-pulse">Loading...</span>
    </div>
  );
}
