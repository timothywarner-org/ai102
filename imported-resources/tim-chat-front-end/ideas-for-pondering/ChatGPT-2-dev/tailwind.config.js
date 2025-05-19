/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    screens: {
      tablet: '480px',
    },
    extend: {
      colors: {
        'app-gray-1': '#171717',
        'app-gray-2': '#212121',
        'app-gray-3': '#2f2f2f;',
        'app-active': '#10a37f',
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('autoprefixer'),
  ],
}
