/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brandGreen: '#10b981',
        brandYellow: '#fbbf24',
      }
    },
  },
  plugins: [],
}
