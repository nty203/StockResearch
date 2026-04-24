import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
    './node_modules/@tremor/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Dark theme design tokens
        bg:       '#0f1117',
        surface:  '#1c1f26',
        card:     '#242836',
        border:   '#2d3147',
        text1:    '#e8eaf0',
        text2:    '#8890a4',
        accent:   '#3b82f6',
        success:  '#22c55e',
        warning:  '#f59e0b',
        error:    '#ef4444',
        gold:     '#f59e0b',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      spacing: {
        '1': '4px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
        '6': '24px',
        '8': '32px',
        '12': '48px',
        '16': '64px',
      },
    },
  },
  plugins: [],
}

export default config
