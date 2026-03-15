import { useEffect, useState } from "react";
import { Button } from "../ui/Button";
import { invalidateCache } from "../../lib/cache";
import { useToast } from "../../contexts/ToastContext";

const STORAGE_KEY = "ia_cache_ttl";

interface TtlOption {
  label: string;
  ms: number;
}

const TTL_OPTIONS: TtlOption[] = [
  { label: "15s", ms: 15_000 },
  { label: "30s", ms: 30_000 },
  { label: "60s", ms: 60_000 },
  { label: "2min", ms: 120_000 },
  { label: "5min", ms: 300_000 },
];

function readTtl(): number {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    const parsed = Number(stored);
    if (!Number.isNaN(parsed) && TTL_OPTIONS.some((o) => o.ms === parsed)) {
      return parsed;
    }
  }
  return 30_000; // default
}

export default function CacheSettings() {
  const { toast } = useToast();
  const [ttl, setTtl] = useState<number>(readTtl);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(ttl));
  }, [ttl]);

  function handleClearCache() {
    invalidateCache();
    toast.success("Cache cleared");
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-gray-400 mb-2">Cache TTL</p>
        <div className="flex items-center gap-1" role="radiogroup" aria-label="Cache TTL">
          {TTL_OPTIONS.map((opt) => (
            <Button
              key={opt.ms}
              size="sm"
              variant={ttl === opt.ms ? "primary" : "ghost"}
              onClick={() => setTtl(opt.ms)}
              aria-checked={ttl === opt.ms}
              role="radio"
            >
              {opt.label}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button size="sm" variant="danger" onClick={handleClearCache}>
          Clear Cache
        </Button>
        <span className="text-xs text-gray-500">
          Current TTL: {TTL_OPTIONS.find((o) => o.ms === ttl)?.label ?? `${ttl}ms`}
        </span>
      </div>
    </div>
  );
}
