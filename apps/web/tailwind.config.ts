import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#ffffff",
        ink: "#13242f",
        muted: "#607077",
        safe: "#0d8c63",
        danger: "#b6402f"
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
        display: ["Space Grotesk", "Segoe UI", "sans-serif"]
      }
    }
  },
  plugins: []
};

export default config;

