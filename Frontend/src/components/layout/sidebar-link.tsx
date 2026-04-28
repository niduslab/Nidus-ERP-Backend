// frontend/src/components/layout/sidebar-link.tsx
//
// One link inside a sidebar section.
//
// RESPONSIBILITIES:
//   - Render the label
//   - Highlight when active (current route)
//   - Show "Soon" badge if coming-soon
//   - Different styling for coming-soon links (muted, smaller hover)
//
// USAGE:
//   <SidebarLink to="/journals" label="Manual Journals" />
//   <SidebarLink to="/sales/customers" label="Customers" comingSoon />

import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';

interface SidebarLinkProps {
  to: string;
  label: string;
  comingSoon?: boolean;
  /**
   * Called when the link is clicked. Used by mobile drawer to close
   * itself after a navigation.
   */
  onNavigate?: () => void;
}

export function SidebarLink({ to, label, comingSoon, onNavigate }: SidebarLinkProps) {
  return (
    <NavLink
      to={to}
      onClick={onNavigate}
      // ── Function form of className ──
      // React Router passes { isActive, isPending } here. We use isActive
      // to highlight the current route. Cleaner than checking the URL
      // ourselves with useLocation.
      className={({ isActive }) =>
        cn(
          // Base layout: padded row, rounded, full width
          'flex items-center justify-between rounded-md px-3 py-1.5 text-sm transition-colors',

          // ── Active state ──
          // When this is the current page, use the sidebar accent token.
          // Defined in tokens.css; auto-flips for dark mode.
          isActive && !comingSoon && 'bg-sidebar-accent text-sidebar-accent-foreground font-medium',

          // ── Inactive states ──
          // Coming-soon links are muted and don't show an "active" effect.
          !isActive && !comingSoon && 'text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
          comingSoon && 'text-muted-foreground hover:bg-sidebar-accent/30 cursor-not-allowed',
        )
      }
    >
      <span className="truncate">{label}</span>
      {comingSoon && (
        <Badge variant="outline" className="ml-2 h-5 text-[10px] font-normal opacity-70">
          Soon
        </Badge>
      )}
    </NavLink>
  );
}