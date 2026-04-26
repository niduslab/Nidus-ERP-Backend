// frontend/src/pages/dashboard/dashboard-placeholder.tsx
//
// TEMPORARY — replaced in Phase 5i with the real dashboard.
// Purpose: prove the protected route + auth state work end-to-end.

import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { authApi } from '@/api/auth';
import { ThemeToggle } from '@/components/theme/theme-toggle';
import { toast } from 'sonner';

export function DashboardPlaceholderPage() {
  const user = useAuthStore((state) => state.user);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const clearAuth = useAuthStore((state) => state.clearAuth);

  async function handleLogout() {
    try {
      if (refreshToken) {
        // Tell the backend to blacklist the refresh token.
        await authApi.logout(refreshToken);
      }
    } catch {
      // Even if the backend call fails (e.g., network error), we still
      // clear local auth — the user pressed Logout, they expect to be
      // logged out regardless.
    } finally {
      clearAuth();
      toast.success('Signed out');
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="container mx-auto flex h-16 items-center justify-between px-6">
          <span className="font-semibold">Dashboard (placeholder)</span>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto p-6">
        <h1 className="text-3xl font-bold tracking-tight">
          Welcome, {user?.full_name}
        </h1>
        <p className="mt-2 text-muted-foreground">
          Logged in as <span className="font-mono">{user?.email}</span>
        </p>
        <p className="mt-6 text-sm text-muted-foreground">
          Real dashboard arrives in Phase 5i.
        </p>
      </main>
    </div>
  );
}