import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        deep: "var(--bg-deep)",
        app: "var(--bg-app)",
        void: "var(--bg-deep)",
        scrim: "var(--scrim)",

        primary: "var(--text-primary)",
        secondary: "var(--text-secondary)",
        tertiary: "var(--text-tertiary)",
        "text-main": "var(--text-primary)",
        "text-muted": "var(--text-secondary)",

        accent: {
          DEFAULT: "var(--accent)",
          hover: "#5ec1ff",
          muted: "rgba(69, 179, 255, 0.15)",
        },
        reasoning: {
          DEFAULT: "var(--reasoning)",
          muted: "rgba(155, 140, 255, 0.15)",
        },
        memory: {
          DEFAULT: "var(--memory)",
          muted: "rgba(47, 212, 194, 0.15)",
        },
        success: {
          DEFAULT: "var(--success)",
          muted: "rgba(52, 199, 123, 0.15)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          muted: "rgba(255, 176, 32, 0.15)",
        },
        danger: {
          DEFAULT: "var(--danger)",
          muted: "rgba(255, 93, 93, 0.15)",
        },
        neutral: {
          DEFAULT: "var(--neutral)",
          muted: "rgba(138, 147, 160, 0.15)",
        },

        "cyan-accent": "var(--accent)",
        "emerald-accent": "var(--success)",
        "rose-accent": "var(--danger)",
        subtle: "rgba(255, 255, 255, 0.08)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["var(--font-jetbrains)", "JetBrains Mono", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        panel: "24px",
        card: "20px",
        stage: "28px",
        pill: "9999px",
      },
      boxShadow: {
        "glass-m1": "inset 0 1px 0 rgba(255,255,255,0.18), 0 8px 40px rgba(0,0,0,0.25)",
        "glass-m2": "inset 0 1px 0 rgba(255,255,255,0.22), 0 12px 48px rgba(0,0,0,0.35)",
        "glass-m3": "inset 0 1px 0 rgba(255,255,255,0.25), 0 24px 80px rgba(0,0,0,0.5)",
        "specular-pill": "inset 0 1px 0 rgba(255,255,255,0.22), 0 2px 8px rgba(0,0,0,0.2)",
      },
      transitionTimingFunction: {
        liquid: "cubic-bezier(0.32, 0.72, 0.28, 1)",
      },
      transitionDuration: {
        instant: "80ms",
        fast: "140ms",
        std: "220ms",
        slow: "320ms",
        glass: "400ms",
      },
    },
  },
  plugins: [],
};

export default config;
