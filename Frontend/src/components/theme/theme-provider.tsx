// frontend/src/components/theme/theme-provider.tsx
//
// Wraps the entire app to provide light/dark mode functionality.
//
// HOW NEXT-THEMES WORKS:
//   - On first load, it reads the user's preference from localStorage.
//     If never set, falls back to system preference (prefers-color-scheme).
//   - When the user toggles themes, it adds/removes `class="dark"` on <html>.
//   - The class change cascades through all CSS variables (see tokens.css).
//   - Persists the choice to localStorage so it survives page reloads.
//
// USAGE:
//   <ThemeProvider>
//     <App />
//   </ThemeProvider>
//
//   Then in any component, use `useTheme()` from 'next-themes' to read
//   or change the current theme.

import { ThemeProvider as NextThemesProvider } from 'next-themes';
import type { ReactNode } from 'react';

interface ThemeProviderProps {
  children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      // attribute='class' makes next-themes manipulate <html class="dark">
      // (the same convention Tailwind's darkMode: 'class' expects).
      attribute="class"

      // 'light' = default to light mode if user has no preference,
      // matching the design choice you locked in earlier.
      defaultTheme="light"

      // Respects the OS-level light/dark preference on first visit only.
      // After that, the user's manual choice is remembered.
      enableSystem={false}

      // Smooths the theme transition — adds a subtle CSS transition.
      // disableTransitionOnChange={false} (default) is fine here.
    >
      {children}
    </NextThemesProvider>
  );
}