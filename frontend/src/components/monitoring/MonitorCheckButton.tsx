import { useState } from "react";
import { runMonitorCheck } from "../../api/endpoints";

interface Props {
  onComplete: () => void;
}

export default function MonitorCheckButton({ onComplete }: Props) {
  const [running, setRunning] = useState(false);

  async function handleClick() {
    setRunning(true);
    try {
      await runMonitorCheck();
      onComplete();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Monitor check failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={running}
      className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-150"
    >
      {running ? "Running check..." : "Run Health Check"}
    </button>
  );
}
