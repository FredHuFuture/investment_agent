import { type InputHTMLAttributes, type SelectHTMLAttributes, forwardRef } from "react";

interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

interface SelectInputProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: { value: string; label: string }[];
}

const baseInputStyles = [
  "w-full bg-gray-800 border rounded-lg px-3 py-2.5 text-gray-100 text-sm",
  "focus:ring-2 focus:ring-accent/40 focus:border-accent outline-none",
  "transition-colors duration-150",
  "placeholder:text-gray-500",
].join(" ");

const errorBorderStyle = "border-down";
const normalBorderStyle = "border-gray-700";

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  ({ label, error, hint, className = "", id, ...rest }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="flex flex-col">
        {label && (
          <label
            htmlFor={inputId}
            className="text-sm font-medium text-gray-300 mb-1.5"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`
            ${baseInputStyles}
            ${error ? errorBorderStyle : normalBorderStyle}
            ${className}
          `}
          {...rest}
        />
        {error && <p className="text-down text-sm mt-1">{error}</p>}
        {hint && !error && (
          <p className="text-xs text-gray-500 mt-1">{hint}</p>
        )}
      </div>
    );
  },
);
TextInput.displayName = "TextInput";

export const SelectInput = forwardRef<HTMLSelectElement, SelectInputProps>(
  ({ label, error, options, className = "", id, ...rest }, ref) => {
    const selectId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="flex flex-col">
        {label && (
          <label
            htmlFor={selectId}
            className="text-sm font-medium text-gray-300 mb-1.5"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={`
            ${baseInputStyles}
            ${error ? errorBorderStyle : normalBorderStyle}
            ${className}
          `}
          {...rest}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {error && <p className="text-down text-sm mt-1">{error}</p>}
      </div>
    );
  },
);
SelectInput.displayName = "SelectInput";
