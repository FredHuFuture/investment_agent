import { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardBody } from "../ui/Card";
import { Button } from "../ui/Button";

const STORAGE_KEY = "risk_parameters";

interface RiskParams {
  maxDrawdown: number;
  maxConcentration: number;
  correlationThreshold: number;
  varConfidence: number;
}

const DEFAULTS: RiskParams = {
  maxDrawdown: 20,
  maxConcentration: 25,
  correlationThreshold: 0.7,
  varConfidence: 95,
};

const VAR_OPTIONS = [90, 95, 99];

function loadParams(): RiskParams {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<RiskParams>;
      return { ...DEFAULTS, ...parsed };
    }
  } catch {
    // ignore parse errors
  }
  return { ...DEFAULTS };
}

export default function RiskParametersCard() {
  const [params, setParams] = useState<RiskParams>(loadParams);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(params));
  }, [params]);

  const update = useCallback(
    <K extends keyof RiskParams>(key: K, value: RiskParams[K]) => {
      setParams((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const resetDefaults = () => setParams({ ...DEFAULTS });

  return (
    <Card>
      <CardHeader
        title="Risk Parameters"
        subtitle="Configure alert thresholds"
        action={
          <Button size="sm" variant="ghost" onClick={resetDefaults}>
            Reset to Defaults
          </Button>
        }
      />
      <CardBody>
        <div className="space-y-5">
          {/* Max Drawdown Warning */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs text-gray-400">Max Drawdown Warning</label>
              <span className="text-xs font-medium text-gray-200">
                {params.maxDrawdown}%
              </span>
            </div>
            <input
              type="range"
              min={5}
              max={50}
              step={1}
              value={params.maxDrawdown}
              onChange={(e) => update("maxDrawdown", Number(e.target.value))}
              className="w-full h-1.5 bg-gray-700 rounded-full appearance-none cursor-pointer accent-blue-500"
            />
            <div className="flex justify-between mt-0.5">
              <span className="text-[10px] text-gray-600">5%</span>
              <span className="text-[10px] text-gray-600">50%</span>
            </div>
          </div>

          {/* Max Position Concentration */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs text-gray-400">Max Position Concentration</label>
              <span className="text-xs font-medium text-gray-200">
                {params.maxConcentration}%
              </span>
            </div>
            <input
              type="range"
              min={5}
              max={50}
              step={1}
              value={params.maxConcentration}
              onChange={(e) => update("maxConcentration", Number(e.target.value))}
              className="w-full h-1.5 bg-gray-700 rounded-full appearance-none cursor-pointer accent-blue-500"
            />
            <div className="flex justify-between mt-0.5">
              <span className="text-[10px] text-gray-600">5%</span>
              <span className="text-[10px] text-gray-600">50%</span>
            </div>
          </div>

          {/* Correlation Alert Threshold */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs text-gray-400">Correlation Alert Threshold</label>
              <span className="text-xs font-medium text-gray-200">
                {params.correlationThreshold.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min={30}
              max={95}
              step={5}
              value={Math.round(params.correlationThreshold * 100)}
              onChange={(e) =>
                update("correlationThreshold", Number(e.target.value) / 100)
              }
              className="w-full h-1.5 bg-gray-700 rounded-full appearance-none cursor-pointer accent-blue-500"
            />
            <div className="flex justify-between mt-0.5">
              <span className="text-[10px] text-gray-600">0.30</span>
              <span className="text-[10px] text-gray-600">0.95</span>
            </div>
          </div>

          {/* VaR Confidence Level */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs text-gray-400">VaR Confidence Level</label>
              <span className="text-xs font-medium text-gray-200">
                {params.varConfidence}%
              </span>
            </div>
            <div className="flex items-center gap-1" role="radiogroup" aria-label="VaR Confidence Level">
              {VAR_OPTIONS.map((opt) => (
                <Button
                  key={opt}
                  size="sm"
                  variant={params.varConfidence === opt ? "primary" : "ghost"}
                  onClick={() => update("varConfidence", opt)}
                  aria-checked={params.varConfidence === opt}
                  role="radio"
                >
                  {opt}%
                </Button>
              ))}
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
