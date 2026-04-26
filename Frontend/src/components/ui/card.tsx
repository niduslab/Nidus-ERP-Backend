// frontend/src/components/ui/card.tsx
//
// The Card primitive — a container with border + bg + padding.
// Decomposed into 6 sub-components so you can build any card layout.
//
// USAGE:
//   <Card>
//     <CardHeader>
//       <CardTitle>Sign in</CardTitle>
//       <CardDescription>Enter your credentials below.</CardDescription>
//     </CardHeader>
//     <CardContent>
//       {/* form fields */}
//     </CardContent>
//     <CardFooter>
//       <Button>Sign in</Button>
//     </CardFooter>
//   </Card>

import * as React from 'react';
import { cn } from '@/lib/utils';

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    // rounded-lg = 8px corners (matches --radius)
    // border = 1px border using --color-border
    // bg-card text-card-foreground = uses --color-card / --color-card-foreground
    //                                (so dark mode flips automatically)
    // shadow-sm = subtle drop shadow for elevation
    className={cn(
      'rounded-lg border bg-card text-card-foreground shadow-sm',
      className,
    )}
    {...props}
  />
));
Card.displayName = 'Card';

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    // flex flex-col space-y-1.5 = vertical layout, 6px gap between children
    // p-6 = 24px padding all around
    className={cn('flex flex-col space-y-1.5 p-6', className)}
    {...props}
  />
));
CardHeader.displayName = 'CardHeader';

const CardTitle = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    // text-2xl = 24px font size, font-semibold = 600 weight
    // leading-none = tight line-height (1.0)
    // tracking-tight = slightly condensed letter-spacing (looks classy on titles)
    className={cn('text-2xl font-semibold leading-none tracking-tight', className)}
    {...props}
  />
));
CardTitle.displayName = 'CardTitle';

const CardDescription = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    // text-sm = 14px, text-muted-foreground = subtle grey color
    className={cn('text-sm text-muted-foreground', className)}
    {...props}
  />
));
CardDescription.displayName = 'CardDescription';

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    // p-6 pt-0 = 24px padding except top (header already has bottom padding)
    className={cn('p-6 pt-0', className)}
    {...props}
  />
));
CardContent.displayName = 'CardContent';

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    // flex items-center = horizontal layout, vertically centered
    // p-6 pt-0 = 24px padding except top
    className={cn('flex items-center p-6 pt-0', className)}
    {...props}
  />
));
CardFooter.displayName = 'CardFooter';

export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
};