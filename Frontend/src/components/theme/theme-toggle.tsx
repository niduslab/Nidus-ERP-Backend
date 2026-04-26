// frontend/src/components/theme/theme-toggle.tsx
//
// A button that toggles between light and dark mode.
// Used in the topbar (and anywhere else you want a theme switcher).
//
// PRO PATTERN — AVOIDS HYDRATION FLASH:
//   When the page first loads, React renders the component before
//   knowing whether the user prefers dark mode. If we naively rendered a
//   "moon" icon assuming light mode, then flipped to "sun" once we knew
//   the actual theme, the user would see a brief icon flicker.
//
//   The `mounted` state gate below ensures we render NOTHING until the
//   theme is known. This is the standard next-themes pattern.

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { Moon, Sun } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ThemeToggleProps {
  /** Optional extra className passed by parent for layout tweaks. */
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  // useTheme returns the current theme + a setter from next-themes.
  // `theme` can be 'light' | 'dark' | 'system' | undefined (during init).
  const { theme, setTheme } = useTheme();

  // Mount gate to prevent hydration flash (see file header comment).
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // While we don't know the theme yet, render an invisible placeholder
  // that takes up the same space — prevents layout jump.
  if (!mounted) {
    return <div className={cn('h-9 w-9', className)} aria-hidden />;
  }

  // The actual toggle button.
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      // ── Tailwind classes explained ──
      // h-9 w-9 = height 36px, width 36px (square button)
      // inline-flex items-center justify-center = centers the icon
      // rounded-md = 6px corner radius (uses --radius - 2px)
      // border = 1px border using --color-border
      // bg-background = page background color
      // hover:bg-accent = light teal hover (uses --color-accent)
      // hover:text-accent-foreground = darker teal text on hover
      // focus-visible:ring-2 focus-visible:ring-ring = keyboard focus ring
      // transition-colors = smooth color change on hover (~150ms)
      className={cn(
        'h-9 w-9 inline-flex items-center justify-center rounded-md',
        'border border-input bg-background',
        'hover:bg-accent hover:text-accent-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'transition-colors',
        className,
      )}
      // aria-label tells screen readers what this button does.
      // Critical for accessibility — the icon alone isn't readable.
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {/* Lucide icons. h-4 w-4 = 16x16px. */}
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}