import { useState } from "react";
import { runMonitorCheck } from "../../api/endpoints";
import { Button } from "../../components/ui/Button";
import { useToast } from "../../contexts/ToastContext";

interface Props {
  onComplete: () => void;
}

export default function MonitorCheckButton({ onComplete }: Props) {
  const [running, setRunning] = useState(false);
  const { toast } = useToast();

  async function handleClick() {
    setRunning(true);
    try {
      await runMonitorCheck();
      toast.success("Health check complete");
      onComplete();
    } catch (err) {
      toast.error(
        "Monitor check failed",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <Button
      variant="primary"
      loading={running}
      onClick={handleClick}
    >
      Run Health Check
    </Button>
  );
}
