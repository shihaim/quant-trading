import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#ffffff",
        ink: "#111827",
        muted: "#64748b",
        safe: "#00e676",
        danger: "#ff4d4d",
        info: "#2563eb",
        canvas: "#f9fafb",
        line: "#f1f5f9"
      },
      fontFamily: {
        sans: ["Pretendard", "Segoe UI", "sans-serif"],
        display: ["Pretendard", "Segoe UI", "sans-serif"]
      }
    }
  },
  plugins: []
};

export default config;

