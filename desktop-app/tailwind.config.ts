import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        void: "var(--bg-void)",
        sidebar: "var(--bg-sidebar)",
        main: "var(--bg-main)",
        surface: "var(--bg-surface)",
        "text-main": "var(--text-main)",
        "text-muted": "var(--text-muted)",
        cyan: {
          accent: "var(--accent-cyan)",
        },
        emerald: {
          accent: "var(--accent-emerald)",
        },
        rose: {
          accent: "var(--accent-rose)",
        },
        subtle: "var(--border-subtle)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      borderColor: {
        subtle: "var(--border-subtle)",
      },
    },
  },
  plugins: [],
};

export default config;
