/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#070b11",
        panel: "#101a28",
        panelSoft: "#132033",
        teal: "#11d9c5",
        tealSoft: "#59f0e0",
      },
      boxShadow: {
        neon: "0 0 0 1px rgba(17,217,197,.3), 0 0 30px rgba(17,217,197,.15)",
      },
      animation: {
        shimmer: "shimmer 2.5s linear infinite",
        pulseborder: "pulseborder 1.5s ease-in-out infinite",
        messagefade: "messagefade 1.8s ease-in-out infinite",
        spinSlow: "spin 2.6s linear infinite",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        pulseborder: {
          "0%, 100%": { opacity: 1 },
          "50%": { opacity: 0.4 },
        },
        messagefade: {
          "0%, 100%": { opacity: 0.5 },
          "50%": { opacity: 1 },
        },
      },
    },
  },
  plugins: [],
};
