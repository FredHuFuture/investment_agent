import { useState } from "react";
import type { BacktestPreset } from "../../lib/backtestPresets";
import {
  getPresets,
  getBuiltInPresets,
  savePreset,
  deletePreset,
} from "../../lib/backtestPresets";

interface Props {
  onLoad: (preset: BacktestPreset) => void;
  getCurrentParams: () => BacktestPreset;
}

const builtInNames = new Set(getBuiltInPresets().map((p) => p.name));

export default function PresetManager({ onLoad, getCurrentParams }: Props) {
  const [presets, setPresets] = useState<BacktestPreset[]>(getPresets);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);
  const [newName, setNewName] = useState("");

  function refresh() {
    setPresets(getPresets());
  }

  function handleLoad() {
    const preset = presets.find((p) => p.name === selected);
    if (preset) onLoad(preset);
  }

  function handleDelete() {
    if (!selected || builtInNames.has(selected)) return;
    deletePreset(selected);
    setSelected("");
    refresh();
  }

  function handleSave() {
    const trimmed = newName.trim();
    if (!trimmed) return;
    const params = getCurrentParams();
    savePreset({ ...params, name: trimmed });
    setSaving(false);
    setNewName("");
    setSelected(trimmed);
    refresh();
  }

  function handleSaveKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") {
      setSaving(false);
      setNewName("");
    }
  }

  const isBuiltIn = builtInNames.has(selected);

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Dropdown */}
      <select
        className="bg-gray-800/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500/50"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        <option value="">-- Select Preset --</option>
        {presets.map((p) => (
          <option key={p.name} value={p.name}>
            {builtInNames.has(p.name) ? `[Built-in] ${p.name}` : p.name}
          </option>
        ))}
      </select>

      {/* Load */}
      <button
        type="button"
        disabled={!selected}
        onClick={handleLoad}
        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150"
      >
        Load
      </button>

      {/* Delete (custom only) */}
      {selected && !isBuiltIn && (
        <button
          type="button"
          onClick={handleDelete}
          className="bg-red-600/80 hover:bg-red-500 text-white rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150"
        >
          Delete
        </button>
      )}

      {/* Save current */}
      {saving ? (
        <div className="flex items-center gap-1.5">
          <input
            autoFocus
            className="bg-gray-800/50 border border-gray-700/50 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder:text-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500/50 w-40"
            placeholder="Preset name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={handleSaveKeyDown}
          />
          <button
            type="button"
            onClick={handleSave}
            disabled={!newName.trim()}
            className="bg-green-600 hover:bg-green-500 disabled:opacity-40 text-white rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150"
          >
            Save
          </button>
          <button
            type="button"
            onClick={() => {
              setSaving(false);
              setNewName("");
            }}
            className="text-gray-400 hover:text-gray-200 text-sm px-2 py-2 transition-colors duration-150"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setSaving(true)}
          className="bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150"
        >
          Save Current
        </button>
      )}
    </div>
  );
}
