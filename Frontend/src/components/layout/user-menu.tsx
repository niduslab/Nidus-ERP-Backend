// frontend/src/components/layout/user-menu.tsx
//
// User profile dropdown in the topbar.
// Shows the user's avatar (with initials fallback) and a menu with:
//   - User info header
//   - Profile link
//   - Help & Documentation
//   - About
//   - Sign out (with backend logout call)
//
// LOGOUT FLOW:
//   1. Call /api/auth/logout/ with the refresh token (backend blacklists it)
//   2. Clear Zustand auth state (which triggers ProtectedRoute redirect)
//   3. Show success toast
//   4. ProtectedRoute detects unauthed → redirects to /login

import { Link } from 'react-router-dom';
import {
  ChevronDown,
  CircleUser,
  HelpCircle,
  Info,
  LogOut,
} from 'lucide-react';
import { toast } from 'sonner';

import { useAuthStore } from '@/stores/auth-store';
import { authApi } from '@/api/auth';

import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

/** Generate initials from a full name. "Rahim Ahmed" → "RA". */
function getInitials(fullName: string | undefined): string {
  if (!fullName) return '?';
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function UserMenu() {
  const user = useAuthStore((state) => state.user);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const clearAuth = useAuthStore((state) => state.clearAuth);

  async function handleSignOut() {
    try {
      // Best effort: tell the backend to blacklist the refresh token.
      // If this fails (network error), we still clear local auth — the
      // user pressed Sign Out, they expect to be signed out.
      if (refreshToken) {
        await authApi.logout(refreshToken);
      }
    } catch {
      // Swallow — local sign-out happens regardless.
    } finally {
      clearAuth();
      toast.success('Signed out');
      // No navigate() needed: clearing auth makes ProtectedRoute redirect
      // to /login automatically on the next render.
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 rounded-md p-1 hover:bg-accent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Open user menu"
        >
          <Avatar className="h-8 w-8">
            {/* No AvatarImage for now — backend has no avatar URLs.
                AvatarFallback shows the user's initials in our brand color. */}
            <AvatarFallback className="bg-primary text-primary-foreground text-xs font-medium">
              {getInitials(user?.full_name)}
            </AvatarFallback>
          </Avatar>
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>

      {/* align="end" anchors the dropdown's right edge to the trigger's right */}
      <DropdownMenuContent align="end" className="w-56">

        {/* User info header — non-interactive label */}
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium leading-none truncate">
              {user?.full_name ?? 'User'}
            </p>
            <p className="text-xs leading-none text-muted-foreground truncate">
              {user?.email}
            </p>
          </div>
        </DropdownMenuLabel>

        <DropdownMenuSeparator />

        {/* Profile — when settings page exists, links to /settings/profile */}
        <DropdownMenuItem asChild>
          <Link to="/settings/profile" className="cursor-pointer">
            <CircleUser className="mr-2 h-4 w-4" />
            Profile
          </Link>
        </DropdownMenuItem>

        {/* Help — external docs link or in-app help (placeholder for now) */}
        <DropdownMenuItem asChild>
          <Link to="/help" className="cursor-pointer">
            <HelpCircle className="mr-2 h-4 w-4" />
            Help & Documentation
          </Link>
        </DropdownMenuItem>

        {/* About — version info, credits */}
        <DropdownMenuItem asChild>
          <Link to="/about" className="cursor-pointer">
            <Info className="mr-2 h-4 w-4" />
            About
          </Link>
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        {/* Sign out — action item, not a link */}
        {/* onSelect runs when clicked AND closes the menu. We use onSelect
            (not onClick) because Radix uses keyboard-friendly select events
            internally. */}
        <DropdownMenuItem
          onSelect={handleSignOut}
          className="cursor-pointer text-destructive focus:text-destructive"
        >
          <LogOut className="mr-2 h-4 w-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}