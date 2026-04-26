// frontend/src/components/ui/input.tsx
//
// The Input primitive — a styled <input> element.
//
// USAGE:
//   <Input type="email" placeholder="you@company.com" />
//   <Input type="password" {...register('password')} />
//
// WHY THIS EXISTS:
//   We could just use <input className="border ..."> everywhere, but then
//   if we want to change input styling globally, we'd edit 100 files.
//   This wrapper centralizes the look. Edit here, every input in the app
//   changes.

import * as React from 'react';
import { cn } from '@/lib/utils';

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<'input'>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        // ── Tailwind classes explained ──
        // flex h-10 = 40px height (matches Button's default size)
        // w-full = takes full width of parent
        // rounded-md = 6px corner radius
        // border border-input = 1px border using --color-input
        // bg-background = page background (so dark mode works)
        // px-3 py-2 = horizontal/vertical padding
        // text-base md:text-sm = larger on mobile (better tap-target),
        //                        smaller on desktop (denser UI)
        // ring-offset-background = focus ring uses page bg as offset
        // file:* = styles for file input button (used when type="file")
        // placeholder:text-muted-foreground = subtle grey placeholder
        // focus-visible:ring-2 ring-ring = teal focus ring (your brand!)
        // disabled:cursor-not-allowed disabled:opacity-50 = greyed when disabled
        className={cn(
          'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-base ring-offset-background',
          'file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground',
          'placeholder:text-muted-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'md:text-sm',
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = 'Input';

export { Input };