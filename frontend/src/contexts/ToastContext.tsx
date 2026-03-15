import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export interface Toast {
  id: string;
  type: "success" | "error" | "info" | "warning";
  title: string;
  message?: string;
  duration?: number;
}

interface ToastHelpers {
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
}

interface ToastContextType {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, "id">) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

const MAX_TOASTS = 5;
const DEFAULT_DURATION = 3000;

let toastCounter = 0;

export const ToastProvider = ({ children }: { children: ReactNode }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const removeToast = useCallback((id: string) => {
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = `toast-${++toastCounter}`;
      const duration = toast.duration ?? DEFAULT_DURATION;

      setToasts((prev) => {
        const next = [...prev, { ...toast, id }];
        // FIFO: keep only the last MAX_TOASTS
        if (next.length > MAX_TOASTS) {
          const removed = next.slice(0, next.length - MAX_TOASTS);
          removed.forEach((r) => {
            const timer = timersRef.current.get(r.id);
            if (timer) {
              clearTimeout(timer);
              timersRef.current.delete(r.id);
            }
          });
          return next.slice(-MAX_TOASTS);
        }
        return next;
      });

      // Auto-remove after duration
      if (duration > 0) {
        const timer = setTimeout(() => {
          removeToast(id);
        }, duration);
        timersRef.current.set(id, timer);
      }
    },
    [removeToast],
  );

  // Cleanup timers on unmount
  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
    };
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextType & { toast: ToastHelpers } => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }

  const { addToast, removeToast, toasts } = context;

  const toast: ToastHelpers = {
    success: (title: string, message?: string) =>
      addToast({ type: "success", title, message }),
    error: (title: string, message?: string) =>
      addToast({ type: "error", title, message }),
    info: (title: string, message?: string) =>
      addToast({ type: "info", title, message }),
    warning: (title: string, message?: string) =>
      addToast({ type: "warning", title, message }),
  };

  return { toasts, addToast, removeToast, toast };
};
