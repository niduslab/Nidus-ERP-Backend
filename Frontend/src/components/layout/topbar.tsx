// frontend/src/components/layout/topbar.tsx
//
// The application topbar.
//
// LAYOUT (left to right):
//   [Hamburger]  [Breadcrumbs]                [Theme] [Bell] [Avatar▾]
//   ↑                                                              ↑
//   visible only on mobile                                          UserMenu
//
// Topbar is a SIBLING of the sidebar inside AppShellLayout. It scrolls
// with the page if you ever want — currently we keep it fixed at the
// top via flex layout in the parent.

import { useState } from 'react';
import { Bell } from 'lucide-react';

import { MobileSidebarTrigger } from './mobile-sidebar-trigger';
import { Breadcrumbs } from './breadcrumbs';
import { NotificationsDrawer } from './notifications-drawer';
import { UserMenu } from './user-menu';
import { ThemeToggle } from '@/components/theme/theme-toggle';

import { cn } from '@/lib/utils';

export function Topbar() {
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  return (
    <>
      <header className={cn(
        'flex h-16 items-center justify-between gap-4',
        'border-b border-border bg-background',
        'px-4 sm:px-6',
        // flex-shrink-0 so the topbar doesn't shrink in a tall content layout
        'flex-shrink-0',
      )}>

        {/* ── Left section: hamburger + breadcrumbs ── */}
        <div className="flex items-center gap-3 min-w-0 flex-1">
          {/* Mobile-only hamburger to open the sidebar drawer */}
          <MobileSidebarTrigger />

          {/* Breadcrumbs — desktop only (mobile hides for space).
              Hidden via Tailwind below md breakpoint. */}
          <div className="hidden md:flex min-w-0">
            <Breadcrumbs />
          </div>
        </div>

        {/* ── Right section: theme toggle, notifications, user menu ── */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <ThemeToggle />

          {/* Notifications bell — opens off-canvas drawer */}
          <button
            type="button"
            onClick={() => setNotificationsOpen(true)}
            className={cn(
              'inline-flex h-9 w-9 items-center justify-center rounded-md',
              'border border-input bg-background',
              'hover:bg-accent hover:text-accent-foreground',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              'transition-colors',
              'relative',
            )}
            aria-label="Open notifications"
          >
            <Bell className="h-4 w-4" />
            {/* Future: notification count badge.
                <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-destructive" /> */}
          </button>

          <UserMenu />
        </div>
      </header>

      {/* ── Notifications drawer ──
          Sibling of the topbar header — controlled by the bell button above.
          Renders nothing visually until opened. */}
      <NotificationsDrawer
        open={notificationsOpen}
        onOpenChange={setNotificationsOpen}
      />
    </>
  );
}