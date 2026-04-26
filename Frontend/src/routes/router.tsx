// frontend/src/routes/router.tsx
//
// React Router config.
// Phase 5e: Forgot/Reset Password pages added — auth flow complete.

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ProtectedRoute } from '@/components/auth/protected-route';
import { LoginPage } from '@/pages/auth/login-page';
import { RegisterPage } from '@/pages/auth/register-page';
import { VerifyEmailPage } from '@/pages/auth/verify-email-page';
import { ForgotPasswordPage } from '@/pages/auth/forgot-password-page';
import { ResetPasswordPage } from '@/pages/auth/reset-password-page';
import { DashboardPlaceholderPage } from '@/pages/dashboard/dashboard-placeholder';
import { NotFoundPage } from '@/pages/errors/not-found';

export const router = createBrowserRouter([
  // ── Public auth routes ──
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/verify-email', element: <VerifyEmailPage /> },
  { path: '/forgot-password', element: <ForgotPasswordPage /> },
  { path: '/reset-password', element: <ResetPasswordPage /> },

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