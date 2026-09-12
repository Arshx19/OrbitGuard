/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        void: {
          900: '#080B12',
          800: '#0A0E17',
          700: '#0F1520',
          600: '#121926',
          500: '#1A2231',
        },
        line: '#1E2836',
        signal: {
          DEFAULT: '#3FD7E8',
          dim: '#1E5A63',
        },
        risk: {
          critical: '#F0475A',
          high: '#F5924A',
          amber: '#F2C94C',
          green: '#3ED598',
        },
        ink: {
          DEFAULT: '#E7ECF3',
          muted: '#8A96A8',
          faint: '#576273',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        panel: '0 0 0 1px rgba(63, 215, 232, 0.05)',
      },
    },
  },
  plugins: [],
}
