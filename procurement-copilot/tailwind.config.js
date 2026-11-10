/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  safelist: [
    // Dynamically generated color classes
    'bg-blue-950/40', 'border-blue-800/30', 'text-blue-300',
    'bg-purple-950/40', 'border-purple-800/30', 'text-purple-300',
    'bg-red-950/40', 'border-red-800/30', 'text-red-300',
    'bg-amber-950/40', 'border-amber-800/30', 'text-amber-300',
    'bg-emerald-950/40', 'border-emerald-800/30', 'text-emerald-300',
    'bg-blue-950/60', 'border-blue-700/40', 'text-blue-300',
    'bg-emerald-950/60', 'border-emerald-700/40', 'text-emerald-300',
    'bg-purple-950/60', 'border-purple-700/40', 'text-purple-300',
    'text-blue-400', 'text-purple-400', 'text-red-400', 'text-amber-400', 'text-emerald-400',
    'bg-blue-950/30', 'bg-emerald-950/30', 'bg-purple-950/30', 'bg-amber-950/30',
    'border-blue-800/20', 'border-emerald-800/20', 'border-purple-800/20', 'border-amber-800/20',
  ],
  plugins: [],
}
