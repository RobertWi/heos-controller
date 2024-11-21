/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./index.html",
    "./static/js/*.js",
    "./templates/**/*.html",
    "./static/css/input.css"
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          primary: '#1a1a1a',
          secondary: '#2d2d2d',
          accent: '#3498db'
        },
        light: {
          primary: '#ffffff',
          secondary: '#f0f0f0',
          accent: '#2c3e50',
          text: '#2c3e50',
          'text-secondary': '#34495e'
        }
      },
      animation: {
        'wave': 'wave 1s ease infinite',
      },
      keyframes: {
        wave: {
          '0%, 100%': { height: '0.5rem' },
          '50%': { height: '1.5rem' },
        },
      },
    },
  },
  plugins: [],
}
