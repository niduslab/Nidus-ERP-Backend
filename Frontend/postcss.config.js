// frontend/postcss.config.js
//
// PostCSS = a tool that transforms CSS at build time.
// Tailwind needs PostCSS to process its directives (@tailwind base, etc.)
// into actual CSS. Autoprefixer adds vendor prefixes (-webkit-, -moz-)
// for older browsers automatically.
//
// You'll never edit this file again. Set-and-forget.

export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};