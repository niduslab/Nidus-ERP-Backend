// frontend/src/pages/auth/login-placeholder.tsx
//
// TEMPORARY — replaced in Phase 5c with the real, beautiful login UI.
//
// PURPOSE OF THIS STUB:
//   Prove end-to-end that:
//     1. Form input → API call → success
//     2. Tokens stored in Zustand → localStorage
//     3. ProtectedRoute lets us into /dashboard
//     4. Token attached to next API call automatically
//
// You can delete this file in Phase 5c when the real login lands.

import { useState, type FormEvent } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export function LoginPlaceholderPage() {
  // useState = component-local memory.
  // First call returns [currentValue, setterFunction].
  // Calling the setter triggers a re-render with the new value.
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const setAuth = useAuthStore((state) => state.setAuth);
  const navigate = useNavigate();

  // location.state is the redirect-after-login payload set by ProtectedRoute.
  // If present, use it; otherwise default to /dashboard.
  const location = useLocation();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const from = (location.state as any)?.from?.pathname ?? '/dashboard';

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();             // Stop the browser from reloading the page
    setSubmitting(true);

    try {
      const response = await authApi.login({ email, password });
      setAuth({
        user: response.data.user,
        accessToken: response.data.tokens.access,
        refreshToken: response.data.tokens.refresh,
      });
      toast.success(`Welcome back, ${response.data.user.full_name}`);
      navigate(from, { replace: true });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      toast.error(err?.response?.data?.message ?? 'Login failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-border bg-card p-8"
      >
        <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="text-sm text-muted-foreground">
          Placeholder login page. Real UI ships in Phase 5c.
        </p>

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />

        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
    </div>
  );
}