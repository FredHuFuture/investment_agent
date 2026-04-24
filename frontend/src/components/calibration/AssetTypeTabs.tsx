export type AssetType = "stock" | "btc" | "eth";

interface Props {
  value: AssetType;
  onChange: (v: AssetType) => void;
}

const TABS: Array<{ value: AssetType; label: string }> = [
  { value: "stock", label: "Stock" },
  { value: "btc", label: "BTC" },
  { value: "eth", label: "ETH" },
];

/**
 * Tab switcher for the three asset types: Stock / BTC / ETH.
 * State is managed by the parent (CalibrationPage); this component is pure presentation.
 */
export default function AssetTypeTabs({ value, onChange }: Props) {
  return (
    <div
      role="tablist"
      className="inline-flex border-b border-gray-800"
      data-testid="cal-asset-type-tabs"
    >
      {TABS.map((tab) => {
        const selected = tab.value === value;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={selected}
            data-testid={`cal-asset-type-tab-${tab.value}`}
            onClick={() => onChange(tab.value)}
            className={[
              "px-4 py-2 text-sm font-medium transition-colors",
              selected
                ? "text-green-400 border-b-2 border-green-400 -mb-px"
                : "text-gray-400 hover:text-gray-200",
            ].join(" ")}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
