// frontend/src/components/ui/button.tsx
//
// The Button component — used everywhere in the app.
// Adapted from shadcn/ui (https://ui.shadcn.com/docs/components/button).
//
// VARIANTS (the `variant` prop):
//   default     — primary teal button (most common)
//   destructive — red button for delete / void actions
//   outline     — transparent with border (secondary actions)
//   secondary   — light grey button (tertiary actions)
//   ghost       — no border or bg, just text (icon buttons, menu items)
//   link        — looks like a hyperlink
//
// SIZES (the `size` prop):
//   default — h-10, px-4 py-2 (most common)
//   sm      — h-9 (compact buttons in toolbars)
//   lg      — h-11 (hero CTAs)
//   icon    — h-10 w-10 (icon-only square buttons)
//
// USAGE:
//   <Button>Save</Button>                          (default variant)
//   <Button variant="destructive">Delete</Button>
//   <Button variant="outline" size="sm">Cancel</Button>
//   <Button disabled>Submitting...</Button>

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

// ── cva() = "class variance authority" ──
// Generates a className based on variant + size props. Mental model:
// it's a typesafe lookup table from {variant, size} → Tailwind classes.
const buttonVariants = cva(
  // ── Base classes — applied to every variant ──
  // inline-flex items-center justify-center: button content is centered
  // gap-2: 8px space between icon and text
  // whitespace-nowrap: button text never wraps
  // rounded-md: 6px corner radius
  // text-sm font-medium: 14px text, semi-bold
  // transition-colors: smooth hover transition
  // focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2:
  //   accessible keyboard focus ring (only shows on Tab navigation, not click)
  // disabled:opacity-50 disabled:pointer-events-none: greyed out when disabled
  // [&_svg]:size-4 [&_svg]:shrink-0: icons inside the button are 16px and don't shrink
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-md px-3',
        lg: 'h-11 rounded-md px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
);

// ── Props ──
// extends ButtonHTMLAttributes = inherits all standard <button> props
//   (onClick, disabled, type, etc.)
// VariantProps<typeof buttonVariants> = adds variant + size with autocomplete
// asChild = polymorphic prop (advanced — lets you render as a different
//           element while keeping all the button styles)
export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

// ── The component ──
// React.forwardRef = lets parent components grab a ref to the underlying
// <button> element (needed for tooltip libraries, focus management, etc.)
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    // If asChild is true, render as Slot (which lets you pass <Link> etc.)
    // Otherwise, render as a plain <button>.
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';

export { Button, buttonVariants };