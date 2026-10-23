import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        bg: "#070b14",
        panel: "#0d1422",
        line: "#1c2638",
        muted: "#8391a7",
        up: "#22c55e",
        down: "#ef4444",
        accent: "#7c9cff",
      },
    },
  },
  plugins: [],
} satisfies Config;
