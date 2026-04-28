// frontend/src/hooks/use-media-query.ts
//
// Custom hook: subscribe to a CSS media query.
//
// USAGE:
//   const isMobile = useMediaQuery('(max-width: 767px)');
//   const prefersDark = useMediaQuery('(prefers-color-scheme: dark)');
//
// HOW IT WORKS:
//   The browser exposes a `matchMedia()` API that returns a MediaQueryList
//   object. It has a `matches` boolean (current state) and emits a 'change'
//   event when the match status flips. We hook into both.
//
// WHY A CUSTOM HOOK:
//   This logic uses useState + useEffect — exactly what custom hooks are
//   for (Concept ⑥ from the architecture lesson). Without it, every
//   component that needs responsive behavior would re-implement these
//   ~15 lines.

import { useEffect, useState } from 'react';

export function useMediaQuery(query: string): boolean {
  // Lazy initial state: read the current match status on mount.
  // useState's argument-as-function form runs ONCE, on first render —
  // skipping the matchMedia call on every subsequent re-render.
  const [matches, setMatches] = useState<boolean>(() => {
    // SSR safety: window is undefined during server-side rendering.
    // We're client-only (Vite), but this guard makes the hook portable.
    if (typeof window === 'undefined') return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mql = window.matchMedia(query);

    // Update state whenever the match status changes (e.g., user resizes
    // the browser, rotates a phone, or toggles their OS dark mode).
    const handler = (event: MediaQueryListEvent) => setMatches(event.matches);

    // Modern API. Older browsers (IE-era) used .addListener — we don't care.
    mql.addEventListener('change', handler);

    // Cleanup on unmount: remove the listener so we don't leak memory
    // or trigger setState on an unmounted component.
    return () => mql.removeEventListener('change', handler);
  }, [query]);

  return matches;
}