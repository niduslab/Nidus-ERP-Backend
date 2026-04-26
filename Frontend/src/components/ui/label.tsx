// frontend/src/components/ui/label.tsx
//
// The Label primitive — a styled <label>.
// Wraps Radix's Label primitive which handles the htmlFor/id linking
// automatically (associating label with input for screen readers).

import * as React from 'react';
import * as LabelPrimitive from '@radix-ui/react-label';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

// cva = class-variance-authority. Same pattern as Button — generates
// className based on variants. Label only has one variant for now,
// but cva makes it easy to add more later.
const labelVariants = cva(
  // Base classes — used always.
  // text-sm font-medium leading-none = small bold-ish text
  // peer-disabled:* = if a sibling .peer is disabled, dim this label too
  //                   (useful when you want clicking the label to toggle
  //                    a sibling input via :peer pattern)
  'text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
);

const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root> &
    VariantProps<typeof labelVariants>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn(labelVariants(), className)}
    {...props}
  />
));
Label.displayName = LabelPrimitive.Root.displayName;

export { Label };