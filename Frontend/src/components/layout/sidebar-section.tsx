// frontend/src/components/layout/sidebar-section.tsx
//
// One collapsible section in the sidebar (e.g., "Sales").
//
// Phase 5f-2 refinements (round 2):
//   - Section header now uses px-3 (was pl-3 pr-2). The OUTER nav
//     container provides the pr-4 buffer for the scrollbar; this row
//     just needs symmetric padding.

import { ChevronDown } from 'lucide-react';
import { useSidebarStore } from '@/stores/sidebar-store';
import type { SidebarSection as SidebarSectionData } from './sidebar-config';
import { SidebarLink } from './sidebar-link';
import { cn } from '@/lib/utils';

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface SidebarSectionProps {
  section: SidebarSectionData;
  isCollapsed: boolean;
  onNavigate?: () => void;
}

export function SidebarSection({
  section,
  isCollapsed,
  onNavigate,
}: SidebarSectionProps) {
  const isOpen = useSidebarStore(
    (state) => state.openSections[section.label] ?? section.defaultOpen ?? true,
  );
  const toggleSection = useSidebarStore((state) => state.toggleSection);

  const Icon = section.icon;

  // ── COLLAPSED MODE — icon only with tooltip ──
  if (isCollapsed) {
    return (
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <div
            className="mx-auto flex h-9 w-9 items-center justify-center rounded-md text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            aria-label={section.label}
          >
            <Icon className="h-4 w-4" />
          </div>
        </TooltipTrigger>
        <TooltipContent side="right">
          {section.label}
        </TooltipContent>
      </Tooltip>
    );
  }

  // ── EXPANDED MODE — header + collapsible children ──
  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={() => toggleSection(section.label)}
        className={cn(
          // px-3 = symmetric left + right padding within this row.
          // The outer <nav> already adds pr-4 to clear the scrollbar.
          'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium',
          'text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
          'transition-colors',
        )}
        aria-expanded={isOpen}
      >
        <Icon className="h-4 w-4 flex-shrink-0" />
        <span className="flex-1 text-left truncate">{section.label}</span>
        <ChevronDown
          className={cn(
            'h-4 w-4 flex-shrink-0 transition-transform',
            isOpen ? 'rotate-180' : 'rotate-0',
          )}
        />
      </button>

      {isOpen && (
        <div className="ml-7 space-y-0.5 border-l border-sidebar-border pl-2">
          {section.links.map((link) => (
            <SidebarLink
              key={link.to}
              to={link.to}
              label={link.label}
              comingSoon={link.comingSoon}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
    </div>
  );
}