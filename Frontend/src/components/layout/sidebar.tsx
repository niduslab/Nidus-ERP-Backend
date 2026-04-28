// frontend/src/components/layout/sidebar.tsx
//
// The top-level Sidebar component.
//
// Phase 5f-2 refinements (round 3):
//   - Pass `isPersistentlyCollapsed` separately from `isCollapsed` so
//     the bottom toggle button reflects the user's preference rather
//     than the transient hover-expand visual state.

import { useEffect, useRef } from 'react';
import { useSidebarStore } from '@/stores/sidebar-store';
import { useMediaQuery } from '@/hooks/use-media-query';
import { SidebarContent } from './sidebar-content';
import { cn } from '@/lib/utils';

import {
  Sheet,
  SheetContent,
} from '@/components/ui/sheet';

export const SIDEBAR_WIDTH = 256;
export const SIDEBAR_WIDTH_COLLAPSED = 64;

const HOVER_LEAVE_DELAY_MS = 250;

export function Sidebar() {
  const collapsed = useSidebarStore((state) => state.collapsed);
  const mobileOpen = useSidebarStore((state) => state.mobileOpen);
  const setMobileOpen = useSidebarStore((state) => state.setMobileOpen);
  const hoverExpanded = useSidebarStore((state) => state.hoverExpanded);
  const setHoverExpanded = useSidebarStore((state) => state.setHoverExpanded);

  const isMobile = useMediaQuery('(max-width: 1023px)');

  const leaveTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (leaveTimerRef.current !== null) {
        clearTimeout(leaveTimerRef.current);
      }
    };
  }, []);

  function handleMouseEnter() {
    if (leaveTimerRef.current !== null) {
      clearTimeout(leaveTimerRef.current);
      leaveTimerRef.current = null;
    }
    if (collapsed) {
      setHoverExpanded(true);
    }
  }

  function handleMouseLeave() {
    if (collapsed) {
      leaveTimerRef.current = window.setTimeout(() => {
        setHoverExpanded(false);
        leaveTimerRef.current = null;
      }, HOVER_LEAVE_DELAY_MS);
    }
  }

  useEffect(() => {
    if (!collapsed && hoverExpanded) {
      setHoverExpanded(false);
    }
  }, [collapsed, hoverExpanded, setHoverExpanded]);

  // ── Mobile rendering: Sheet drawer ──
  if (isMobile) {
    return (
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-72 p-0 bg-sidebar">
          <SidebarContent
            isCollapsed={false}
            onNavigate={() => setMobileOpen(false)}
          />
        </SheetContent>
      </Sheet>
    );
  }

  // ── Desktop rendering ──
  // visualWidth drives the actual rendered width — same value for the
  // wrapper and the aside, which is what gives us the push-content-while-
  // animating behavior from the previous round.
  const isVisuallyExpanded = !collapsed || hoverExpanded;
  const visualWidth = isVisuallyExpanded ? SIDEBAR_WIDTH : SIDEBAR_WIDTH_COLLAPSED;

  return (
    <div
      className={cn(
        'relative flex-shrink-0',
        'transition-[width] duration-500 ease-in-out',
      )}
      style={{ width: visualWidth }}
    >
      <aside
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className={cn(
          'absolute inset-y-0 left-0 w-full',
          'border-r border-sidebar-border bg-sidebar',
        )}
      >
        <SidebarContent
          // VISUAL — controls how nav renders (icons vs labels).
          // False during hover-expand → user sees full content.
          isCollapsed={!isVisuallyExpanded}

          // PERSISTENT — controls the bottom toggle icon.
          // Stays true during hover-expand → bottom arrow stays as ">>".
          isPersistentlyCollapsed={collapsed}

          showCollapseToggle
        />
      </aside>
    </div>
  );
}