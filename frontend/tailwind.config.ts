import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    fontFamily: {
      display: ['"Source Serif 4"', "Georgia", "serif"],
      sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
      mono: ['"JetBrains Mono"', "monospace"],
    },
    extend: {
      colors: {
        gray: {
          50: "rgb(var(--gray-50) / <alpha-value>)",
          100: "rgb(var(--gray-100) / <alpha-value>)",
          200: "rgb(var(--gray-200) / <alpha-value>)",
          300: "rgb(var(--gray-300) / <alpha-value>)",
          400: "rgb(var(--gray-400) / <alpha-value>)",
          500: "rgb(var(--gray-500) / <alpha-value>)",
          600: "rgb(var(--gray-600) / <alpha-value>)",
          700: "rgb(var(--gray-700) / <alpha-value>)",
          800: "rgb(var(--gray-800) / <alpha-value>)",
          900: "rgb(var(--gray-900) / <alpha-value>)",
          950: "rgb(var(--gray-950) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          light: "rgb(var(--accent-light) / <alpha-value>)",
          dark: "rgb(var(--accent-dark) / <alpha-value>)",
          surface: "rgb(var(--accent-surface) / <alpha-value>)",
        },
        up: {
          DEFAULT: "rgb(var(--up) / <alpha-value>)",
          surface: "rgb(var(--up-surface) / <alpha-value>)",
        },
        down: {
          DEFAULT: "rgb(var(--down) / <alpha-value>)",
          surface: "rgb(var(--down-surface) / <alpha-value>)",
        },
        caution: {
          DEFAULT: "rgb(var(--caution) / <alpha-value>)",
          surface: "rgb(var(--caution-surface) / <alpha-value>)",
        },
      },
      borderRadius: {
        card: "10px",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        "card-hover": "var(--shadow-card-hover)",
        elevated: "var(--shadow-elevated)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
        "slide-down": {
          from: { opacity: "0", transform: "translateY(-4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up":
          "fade-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-in": "fade-in 0.3s ease-out both",
        "slide-in-right":
          "slide-in-right 0.25s cubic-bezier(0.16, 1, 0.3, 1) both",
        "slide-down":
          "slide-down 0.3s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
    },
  },
  plugins: [],
} satisfies Config;
