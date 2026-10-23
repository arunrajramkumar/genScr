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
        bg: "#030508",
        panel: "#0a0f17",
        line: "#161e2b",
        muted: "#7d8aa0",
        up: "#00d47e",
        down: "#ff4d5e",
        accent: "#7c9cff",
        gold: "#f5b942",
      },
      boxShadow: {
        "glow-up": "0 0 24px -4px rgba(0,212,126,0.45)",
        "glow-down": "0 0 24px -4px rgba(255,77,94,0.45)",
        "glow-accent": "0 0 32px -6px rgba(124,156,255,0.5)",
      },
      keyframes: {
        marquee: { from: { transform: "translateX(0)" }, to: { transform: "translateX(-50%)" } },
        "fade-up": { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "none" } },
        pulse_dot: { "0%,100%": { opacity: "1" }, "50%": { opacity: "0.35" } },
      },
      animation: {
        marquee: "marquee 60s linear infinite",
        "fade-up": "fade-up 0.5s ease-out both",
        "pulse-dot": "pulse_dot 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
