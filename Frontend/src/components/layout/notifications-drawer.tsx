// frontend/src/components/layout/notifications-drawer.tsx
//
// Off-canvas notifications panel triggered from the topbar bell icon.
// Slides in from the right.
//
// CURRENT STATE: empty-state placeholder. The backend doesn't yet have
// a notifications model. When that ships, we'll fetch via TanStack Query
// and render the list here. Architecture is ready for that swap.

import { Bell, BellOff } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';

interface NotificationsDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NotificationsDrawer({ open, onOpenChange }: NotificationsDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notifications
          </SheetTitle>
          <SheetDescription>
            Stay informed about activity across your company.
          </SheetDescription>
        </SheetHeader>

        {/* ── Empty state ──
            Standard pattern: large icon, title, supporting copy.
            When notifications data lands, this becomes a list. */}
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
            <BellOff className="h-5 w-5 text-muted-foreground" />
          </div>
          <h3 className="mt-4 text-base font-medium">You're all caught up</h3>
          <p className="mt-1 text-sm text-muted-foreground max-w-xs">
            Notifications about journal posts, member changes, and report
            exports will appear here.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}