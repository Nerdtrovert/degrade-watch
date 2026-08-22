/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#0066FF",
        "primary-hover": "#0055CC",
        "primary-active": "#0044AA",
        background: "#F9FAFB",
        surface: "#FFFFFF",
        "text-primary": "#1F2937",
        "text-secondary": "#4B5563",
        border: "#D1D5DB",
        success: "#10B981",
        warning: "#F59E0B",
        critical: "#EF4444",
        info: "#3B82F6",
        danger: "#EF4444",
      },
      spacing: {
        0: "0px",
        1: "4px",
        2: "8px",
        3: "12px",
        4: "16px",
        5: "24px",
        6: "32px",
      },
      borderRadius: {
        sm: "4px",
        md: "8px",
      },
      boxShadow: {
        subtle: "0 1px 2px rgba(0,0,0,0.05)",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
      fontSize: {
        display: ["2.5rem", { lineHeight: "1.2" }],
        title: ["2rem", { lineHeight: "1.3" }],
        heading: ["1.5rem", { lineHeight: "1.4" }],
        "card-heading": ["1.125rem", { lineHeight: "1.5" }],
        body: ["1rem", { lineHeight: "1.6" }],
        small: ["0.875rem", { lineHeight: "1.6" }],
        caption: ["0.75rem", { lineHeight: "1.5" }],
        table: ["0.875rem", { lineHeight: "1.5" }],
      },
    },
  },
  plugins: [],
};