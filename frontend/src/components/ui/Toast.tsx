import { useToast } from "../../contexts/ToastContext";
import type { Toast as ToastType } from "../../contexts/ToastContext";
import "./toast-animations.css";

const typeStyles: Record<ToastType["type"], { border: string; icon: string; bg: string }> = {
  success: {
    border: "border-green-500/50",
    icon: "text-green-400",
    bg: "bg-green-500/10",
  },
  error: {
    border: "border-red-500/50",
    icon: "text-red-400",
    bg: "bg-red-500/10",
  },
  info: {
    border: "border-accent/50",
    icon: "text-accent-light",
    bg: "bg-accent/10",
  },
  warning: {
    border: "border-yellow-500/50",
    icon: "text-yellow-400",
    bg: "bg-yellow-500/10",
  },
};

const icons: Record<ToastType["type"], JSX.Element> = {
  success: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  ),
  error: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  ),
  info: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z" />
    </svg>
  ),
  warning: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
    </svg>
  ),
};

const ToastItem = ({
  toast,
  onClose,
}: {
  toast: ToastType;
  onClose: () => void;
}) => {
  const styles = typeStyles[toast.type];

  return (
    <div
      className={`
        toast-enter
        flex items-start gap-3
        rounded-lg border shadow-lg
        ${styles.border} ${styles.bg}
        bg-gray-900 p-4 min-w-[300px] max-w-[420px]
      `}
      role="alert"
    >
      <div className={`flex-shrink-0 ${styles.icon}`}>
        {icons[toast.type]}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-100">{toast.title}</p>
        {toast.message && (
          <p className="mt-1 text-sm text-gray-400">{toast.message}</p>
        )}
      </div>

      <button
        onClick={onClose}
        className="flex-shrink-0 text-gray-500 hover:text-gray-300 transition-colors"
        aria-label="Close notification"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
};

export const ToastContainer = () => {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem
          key={toast.id}
          toast={toast}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
};
