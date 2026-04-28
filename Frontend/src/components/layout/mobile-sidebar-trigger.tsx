// frontend/src/components/layout/mobile-sidebar-trigger.tsx
//
// The hamburger button that opens the mobile sidebar drawer.
// Placed in the topbar — visible only on mobile (hidden on desktop via
// Tailwind's lg:hidden class).
//
// USAGE (in topbar — Phase 5f-3):
//   <MobileSidebarTrigger />

import { Menu } from 'lucide-react';
import { useSidebarStore } from '@/stores/sidebar-store';
import { cn } from '@/lib/utils';

interface MobileSidebarTriggerProps {
  className?: string;
}

export function MobileSidebarTrigger({ className }: MobileSidebarTriggerProps) {
  const setMobileOpen = useSidebarStore((state) => state.setMobileOpen);

  return (
    <button
      type="button"
      onClick={() => setMobileOpen(true)}
      // lg:hidden = hidden on screens >= 1024px (desktop has fixed sidebar)
      className={cn(
        'inline-flex h-9 w-9 items-center justify-center rounded-md',
        'border border-input bg-background',
        'hover:bg-accent hover:text-accent-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'lg:hidden',
        className,
      )}
      aria-label="Open navigation menu"
    >
      <Menu className="h-4 w-4" />
    </button>
  );
}