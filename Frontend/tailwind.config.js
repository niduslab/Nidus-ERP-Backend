// frontend/tailwind.config.js
//
// Tailwind CSS configuration.
//
// THIS FILE'S JOB:
//   Tell Tailwind which CSS classes to generate, and bind them to the
//   CSS variables defined in src/styles/tokens.css.
//
// MENTAL MODEL:
//   Tailwind = a CSS class generator. By default it ships with thousands
//   of classes (bg-blue-500, text-xl, p-4, etc.). We OVERRIDE the
//   `theme.extend.colors` block to make `bg-primary`, `text-primary`,
//   `border-primary` read from our own design tokens.
//
//   When you write `class="bg-primary"` in a component, Tailwind generates:
//       .bg-primary { background-color: hsl(var(--color-primary)); }
//   That CSS variable is defined in tokens.css with different values for
//   light and dark mode.

/** @type {import('tailwindcss').Config} */
export default {
  // ── Files Tailwind should scan for class names ──
  // Tailwind only generates CSS for classes it actually finds. This makes
  // production builds tiny (~10 KB instead of 4 MB). The patterns cover
  // every TypeScript / TSX file in src/ and the root index.html.
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],

  // ── Dark mode strategy ──
  // 'class' = dark mode activates when <html class="dark"> is set.
  // The alternative ('media') uses prefers-color-scheme only — but then we
  // can't have a manual toggle. We'll use next-themes to flip the class.
  darkMode: 'class',

  theme: {
    // ── Custom screen breakpoints ──
    // Tailwind defaults are sm:640, md:768, lg:1024, xl:1280, 2xl:1536.
    // We use these defaults for now. To change later, add a `screens`
    // object here.

    // ── extend = ADD to defaults (don't replace them) ──
    // The keys below become Tailwind utilities:
    //   colors.primary → bg-primary, text-primary, border-primary, etc.
    //   borderRadius.lg → rounded-lg
    extend: {
      // ── Colors ──
      // Each color references a CSS variable. The variable is defined in
      // tokens.css and changes value in dark mode.
      //
      // The "hsl(var(--x))" syntax is what lets us add opacity later:
      //   bg-primary/50 = 50% opaque primary color
      // For this to work, the CSS variable must contain SPACE-SEPARATED
      // HSL values WITHOUT the surrounding hsl(...). See tokens.css.
      colors: {
        // ── Surface colors ──
        // background = the page background; foreground = body text on it.
        // Naming convention: <surface> + "-foreground" = text color on it.
        // This pattern comes from shadcn/ui — the most readable in the industry.
        background: 'hsl(var(--color-background))',
        foreground: 'hsl(var(--color-foreground))',

        // ── Card surfaces (slightly elevated panels) ──
        card: {
          DEFAULT: 'hsl(var(--color-card))',
          foreground: 'hsl(var(--color-card-foreground))',
        },

        // ── Popover (dropdowns, tooltips) ──
        popover: {
          DEFAULT: 'hsl(var(--color-popover))',
          foreground: 'hsl(var(--color-popover-foreground))',
        },

        // ── Primary brand color (your teal) ──
        // Used for primary buttons, active sidebar items, links.
        primary: {
          DEFAULT: 'hsl(var(--color-primary))',
          foreground: 'hsl(var(--color-primary-foreground))',
        },

        // ── Secondary (neutral surfaces, secondary buttons) ──
        secondary: {
          DEFAULT: 'hsl(var(--color-secondary))',
          foreground: 'hsl(var(--color-secondary-foreground))',
        },

        // ── Muted (subtle text, placeholders, disabled states) ──
        muted: {
          DEFAULT: 'hsl(var(--color-muted))',
          foreground: 'hsl(var(--color-muted-foreground))',
        },

        // ── Accent (hover states, subtle highlights) ──
        accent: {
          DEFAULT: 'hsl(var(--color-accent))',
          foreground: 'hsl(var(--color-accent-foreground))',
        },

        // ── Destructive (delete buttons, error messages, void status) ──
        destructive: {
          DEFAULT: 'hsl(var(--color-destructive))',
          foreground: 'hsl(var(--color-destructive-foreground))',
        },

        // ── Status colors (ERP-specific) ──
        // For journal status pills, account active/inactive indicators, etc.
        // These are SEMANTIC names, not literal colors. If you ever change
        // your mind about what "success" looks like, change tokens.css only.
        success: {
          DEFAULT: 'hsl(var(--color-success))',
          foreground: 'hsl(var(--color-success-foreground))',
        },
        warning: {
          DEFAULT: 'hsl(var(--color-warning))',
          foreground: 'hsl(var(--color-warning-foreground))',
        },
        info: {
          DEFAULT: 'hsl(var(--color-info))',
          foreground: 'hsl(var(--color-info-foreground))',
        },

        // ── Borders & inputs ──
        // border = card/section dividers
        // input  = form input borders
        // ring   = focus ring (the glow when an input has keyboard focus)
        border: 'hsl(var(--color-border))',
        input: 'hsl(var(--color-input))',
        ring: 'hsl(var(--color-ring))',

        // ── Sidebar (a slightly different surface — common in ERP apps) ──
        sidebar: {
          DEFAULT: 'hsl(var(--color-sidebar))',
          foreground: 'hsl(var(--color-sidebar-foreground))',
          accent: 'hsl(var(--color-sidebar-accent))',
          'accent-foreground': 'hsl(var(--color-sidebar-accent-foreground))',
          border: 'hsl(var(--color-sidebar-border))',
        },
      },

      // ── Border radius scale ──
      // Centralized so changing --radius in tokens.css updates everything.
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },

      // ── Typography ──
      // We use the system font stack (no Google Fonts download required).
      // These sans-serifs look professional on every OS:
      //   - Windows: Segoe UI
      //   - macOS:   -apple-system / SF Pro
      //   - Linux:   Inter / Roboto
      fontFamily: {
        sans: [
          'Inter',  // If installed (we'll add it via CSS later, optional)
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
        // Mono font for account codes, amounts, JE numbers.
        mono: [
          'JetBrains Mono',
          'Menlo',
          'Monaco',
          'Consolas',
          'Liberation Mono',
          'Courier New',
          'monospace',
        ],
      },

      // ── Custom animations ──
      // Used by shadcn/ui components (Dialog open/close, Dropdown slide-in).
      // tailwindcss-animate plugin provides the keyframes.
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to:   { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to:   { height: '0' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up':   'accordion-up 0.2s ease-out',
      },
    },
  },

  // ── Plugins ──
  // tailwindcss-animate adds animation utility classes shadcn/ui needs.
  plugins: [
    require('tailwindcss-animate'),
  ],
};