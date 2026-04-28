// frontend/src/components/ui/badge.tsx
//
// Badge — small colored pill for status, labels, counts.
// Used in Phase 5f-2 for "Soon" badges next to coming-soon links.
// Used in later phases for journal status (Draft/Posted/Void), notification
// counts, account-active indicators, etc.
//
// USAGE:
//   <Badge>New</Badge>
//   <Badge variant="success">Posted</Badge>
//   <Badge variant="warning">Draft</Badge>
//   <Badge variant="destructive">Void</Badge>
//
// VARIANTS map to your design tokens — add more in tokens.css and here
// if you need them.

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        secondary: 'border-transparent bg-secondary text-secondary-foreground',
        destructive: 'border-transparent bg-destructive text-destructive-foreground',
        success: 'border-transparent bg-success text-success-foreground',
        warning: 'border-transparent bg-warning text-warning-foreground',
        info: 'border-transparent bg-info text-info-foreground',
        outline: 'text-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };