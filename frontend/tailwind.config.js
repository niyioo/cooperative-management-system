/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Sampled from EMDI's official logo.
        brand: {
          50: '#eef1fa',
          100: '#dce2f4',
          200: '#b6c1e7',
          500: '#3a4fb6',
          600: '#293c9c',
          700: '#213180',
          800: '#1a2766',
          900: '#141d4d',
        },
        accent: '#0872ef',
        emblem: '#5202d7',
      },
      fontFamily: {
        sans: ['"Segoe UI"', 'system-ui', '-apple-system', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
