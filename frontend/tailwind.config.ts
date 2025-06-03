import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}", // If using pages router
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}", // For App router
  ],
  theme: {
    extend: {
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":
          "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
      },
      // Add custom "mech" theme colors/fonts/spacing here later
      colors: {
        'mech-primary': '#0A0F1A', // Dark blue/grey
        'mech-secondary': '#1B2A41', // Lighter blue/grey
        'mech-accent': '#00A8E8',  // Bright blue accent
        'mech-text-light': '#E0E0E0',
        'mech-text-dark': '#A0A0A0',
      }
    },
  },
  plugins: [],
};
export default config;
