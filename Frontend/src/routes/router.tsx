// frontend/src/routes/router.tsx
//
// React Router config.
// Phase 5d: Register + Verify Email pages added.

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ProtectedRoute } from '@/components/auth/protected-route';
import { LoginPage } from '@/pages/auth/login-page';
import { RegisterPage } from '@/pages/auth/register-page';
import { VerifyEmailPage } from '@/pages/auth/verify-email-page';
import { DashboardPlaceholderPage } from '@/pages/dashboard/dashboard-placeholder';
import { NotFoundPage } from '@/pages/errors/not-found';
import { ComingSoonPage } from '@/pages/errors/coming-soon';

export const router = createBrowserRouter([
  // ── Public auth routes ──
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/verify-email', element: <VerifyEmailPage /> },

  // Forgot/reset still placeholders — Phase 5e ships them.
  {
    path: '/forgot-password',
    element: <ComingSoonPage title="Forgot password" subtitle="Coming in Phase 5e" />,
  },
  {
    path: '/reset-password',
    element: <ComingSoonPage title="Reset password" subtitle="Coming in Phase 5e" />,
  },

  // ── Protected routes ──
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/dashboard', element: <DashboardPlaceholderPage /> },
    ],
  },

  // ── Root redirect ──
  { path: '/', element: <Navigate to="/dashboard" replace /> },

  // ── 404 catch-all ──
  { path: '*', element: <NotFoundPage /> },
]);