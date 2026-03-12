export default function WarningsBanner({ warnings }: { warnings: string[] }) {
  if (!warnings || warnings.length === 0) return null;

  return (
    <div className="rounded-lg bg-amber-400/10 border border-amber-400/30 px-4 py-3 text-sm text-amber-400">
      <div className="flex items-start gap-2">
        <span className="shrink-0 mt-0.5">&#9888;</span>
        <div>
          {warnings.length === 1 ? (
            <span>{warnings[0]}</span>
          ) : (
            <ul className="list-disc list-inside space-y-0.5">
              {warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
