// frontend/src/components/layout/sidebar-content.tsx
//
// The CONTENTS of the sidebar (logo + nav tree + collapse footer).
//
// IMPORTANT NAMING DISTINCTION (round 3 refinement):
//
//   isCollapsed (visual)
//     → Drives whether content renders in icon-only mode.
//     → True when sidebar is visually narrow (64px).
//     → False when sidebar is visually full-width (256px),
//       INCLUDING during hover-expand on a collapsed sidebar.
//
//   isPersistentlyCollapsed (preference)
//     → Drives the bottom toggle button's icon and label.
//     → Reflects the user's SAVED preference.
//     → Stays "true" during hover-expand because the user's
//       persisted choice hasn't changed.
//
// The bottom toggle's chevron always reflects the user's PREFERENCE so
// it doesn't flicker during hover-peek. The user's collapse choice is
// stable; the visual state is transient.

import { Link } from 'react-router-dom';
import { ChevronsLeft, ChevronsRight } from 'lucide-react';

import { useSidebarStore } from '@/stores/sidebar-store';
import { SIDEBAR_ENTRIES } from './sidebar-config';
import { SidebarSection } from './sidebar-section';
import { cn } from '@/lib/utils';

import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface SidebarContentProps {
  /**
   * Visual collapse state — controls how the nav RENDERS (icons-only
   * vs full content). When hover-expand is active on a collapsed
   * sidebar, this should be `false` so the user sees full nav.
   */
  isCollapsed: boolean;

  /**
   * Persistent collapse preference — controls the bottom TOGGLE's
   * appearance only. Equal to the user's saved `collapsed` flag.
   * Stays `true` during hover-expand so the icon/text doesn't flicker.
   *
   * Optional because the mobile drawer doesn't show the toggle button.
   */
  isPersistentlyCollapsed?: boolean;

  /** Called when a link is clicked. Used by mobile drawer to close itself. */
  onNavigate?: () => void;

  /** Whether to show the desktop collapse toggle at the bottom. */
  showCollapseToggle?: boolean;
}

export function SidebarContent({
  isCollapsed,
  isPersistentlyCollapsed,
  onNavigate,
  showCollapseToggle = false,
}: SidebarContentProps) {
  const toggleCollapsed = useSidebarStore((state) => state.toggleCollapsed);

  // ── Falls back to the visual collapse state if the parent didn't pass
  //    a separate persistent flag. Keeps the mobile drawer rendering
  //    sensibly even though it never shows the toggle. ──
  const togglePrefIsCollapsed = isPersistentlyCollapsed ?? isCollapsed;

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">

      {/* ── Top: Logo / Brand ── */}
      <div className={cn(
        'flex h-16 items-center border-b border-sidebar-border',
        isCollapsed ? 'justify-center px-2' : 'px-6',
      )}>
        <Link to="/dashboard" className="flex items-center gap-2 overflow-hidden" onClick={onNavigate}>
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold text-sm flex-shrink-0">
            N
          </div>
          {!isCollapsed && (
            <span className="text-lg font-semibold tracking-tight whitespace-nowrap">
              Nidus ERP
            </span>
          )}
        </Link>
      </div>

      {/* ── Middle: Scrollable nav ── */}
      <ScrollArea className="flex-1">
        <nav className={cn(
          'space-y-1 py-4',
          isCollapsed ? 'px-2' : 'pl-3 pr-4',
        )}>
          {SIDEBAR_ENTRIES.map((entry, idx) => {
            // ── Top-level link (Home, Budget) ──
            if (entry.kind === 'link') {
              if (isCollapsed) {
                const Icon = entry.icon;
                return (
                  <Tooltip key={idx} delayDuration={300}>
                    <TooltipTrigger asChild>
                      <Link
                        to={entry.to}
                        onClick={onNavigate}
                        className="mx-auto flex h-9 w-9 items-center justify-center rounded-md text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                      >
                        <Icon className="h-4 w-4" />
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      {entry.label}
                    </TooltipContent>
                  </Tooltip>
                );
              }
              const Icon = entry.icon;
              return (
                <div key={idx}>
                  <Link
                    to={entry.to}
                    onClick={onNavigate}
                    className={cn(
                      'flex items-center gap-2 rounded-md py-2 pl-3 pr-3 text-sm font-medium',
                      'text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
                      entry.comingSoon && 'text-muted-foreground',
                    )}
                  >
                    <Icon className="h-4 w-4 flex-shrink-0" />
                    <span className="flex-1 truncate">{entry.label}</span>
                    {entry.comingSoon && (
                      <span className="text-[10px] uppercase opacity-70 flex-shrink-0">Soon</span>
                    )}
                  </Link>
                </div>
              );
            }

            // ── Section ──
            return (
              <SidebarSection
                key={idx}
                section={entry.section}
                isCollapsed={isCollapsed}
                onNavigate={onNavigate}
              />
            );
          })}
        </nav>
      </ScrollArea>

      {/* ── Bottom: Collapse toggle ──
          Uses the PERSISTENT preference (togglePrefIsCollapsed), NOT the
          visual state. So during hover-peek over a collapsed sidebar:
            - Icon stays as ChevronsRight (>>)
            - "Collapse" text doesn't appear
            - Button is centered (not left-aligned with text)
          The user's saved preference is what's communicated, not the
          transient hover effect. */}
      {showCollapseToggle && (
        <div className="border-t border-sidebar-border p-2">
          <button
            type="button"
            onClick={toggleCollapsed}
            className={cn(
              'flex w-full items-center gap-2 rounded-md py-2 text-sm',
              'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
              'transition-colors',
              togglePrefIsCollapsed ? 'justify-center px-2' : 'pl-3 pr-3',
            )}
            aria-label={togglePrefIsCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {togglePrefIsCollapsed ? (
              <ChevronsRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronsLeft className="h-4 w-4" />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}