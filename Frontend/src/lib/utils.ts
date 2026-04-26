// frontend/src/lib/utils.ts
//
// Shared utility helpers. The most important one: `cn()`.

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * cn = "className" — merges Tailwind classes intelligently.
 *
 * WHY YOU NEED THIS:
 *   When you compose components, you often want to pass class names down
 *   AND override some defaults. Two problems arise:
 *
 *   1. CONDITIONAL CLASSES: You want some classes only when a condition is true.
 *      Without cn:
 *        const className = `p-4 ${isActive ? 'bg-primary' : 'bg-secondary'}`;
 *      With cn:
 *        const className = cn('p-4', isActive ? 'bg-primary' : 'bg-secondary');
 *      Cleaner, and `cn` accepts arrays, objects, falsy values automatically.
 *
 *   2. CONFLICTING TAILWIND CLASSES: Two classes that affect the same property.
 *      cn('p-4', 'p-8')                  → 'p-8'  (twMerge keeps the LAST one)
 *      cn('bg-red-500', 'bg-blue-500')   → 'bg-blue-500'
 *      Without twMerge, BOTH classes would land in the HTML and the browser
 *      would pick one based on CSS specificity rules (unpredictable).
 *
 * EXAMPLES:
 *   cn('px-4 py-2', 'bg-primary')             → 'px-4 py-2 bg-primary'
 *   cn('px-4 py-2', isLoading && 'opacity-50') → 'px-4 py-2 opacity-50' (if loading)
 *   cn('p-4', { 'bg-primary': active })       → 'p-4 bg-primary' (if active)
 *
 * RULE OF THUMB:
 *   Anywhere you'd write a className that combines literal strings + variables,
 *   wrap it in cn(...). Never use string concatenation for classes.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}