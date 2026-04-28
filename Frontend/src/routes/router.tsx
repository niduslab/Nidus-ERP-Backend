// frontend/src/routes/router.tsx
//
// React Router config — Phase 5f-3.
//
// STRUCTURE:
//   /login, /register, /verify-email, /forgot-password, /reset-password
//     → public, no shell
//
//   Everything else
//     → ProtectedRoute → AppShellLayout → matched child route
//
// COMING SOON:
//   Most sidebar links don't have real backend yet. We route them all to
//   ComingSoonPage so users see a friendly "Coming in Step X" message
//   instead of a 404. As each module ships, replace the corresponding
//   route's element with the real page.

import { createBrowserRouter, Navigate } from 'react-router-dom';

import { ProtectedRoute } from '@/components/auth/protected-route';
import { AppShellLayout } from '@/components/layout/app-shell-layout';

// Auth pages
import { LoginPage } from '@/pages/auth/login-page';
import { RegisterPage } from '@/pages/auth/register-page';
import { VerifyEmailPage } from '@/pages/auth/verify-email-page';
import { ForgotPasswordPage } from '@/pages/auth/forgot-password-page';
import { ResetPasswordPage } from '@/pages/auth/reset-password-page';

// In-shell pages
import { DashboardPage } from '@/pages/dashboard/dashboard-page';

// Errors
import { NotFoundPage } from '@/pages/errors/not-found';
import { ComingSoonPage } from '@/pages/errors/coming-soon';

export const router = createBrowserRouter([

  // ══════════════════════════════════════════════════
  // PUBLIC AUTH ROUTES
  // ══════════════════════════════════════════════════
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/verify-email', element: <VerifyEmailPage /> },
  { path: '/forgot-password', element: <ForgotPasswordPage /> },
  { path: '/reset-password', element: <ResetPasswordPage /> },

  // ══════════════════════════════════════════════════
  // PROTECTED ROUTES — all nested under AppShellLayout
  // ══════════════════════════════════════════════════
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShellLayout />,
        children: [

          // ── Home ──
          { path: '/dashboard', element: <DashboardPage /> },

          // ── Accounting (built — placeholder Coming Soon for now) ──
          // These will be replaced with real components in 5g, 5h, etc.
          { path: '/coa', element: <ComingSoonPage title="Chart of Accounts" subtitle="Coming in Phase 5h" /> },
          { path: '/journals', element: <ComingSoonPage title="Manual Journals" subtitle="Coming in Phase 5j" /> },
          { path: '/journals/bulk', element: <ComingSoonPage title="Bulk Update" subtitle="Coming in Phase 5j" /> },

          // ── Sales (all coming soon — Step 8 backend) ──
          { path: '/sales/customers', element: <ComingSoonPage title="Customers" subtitle="Backend coming in Step 6" /> },
          { path: '/sales/quotations', element: <ComingSoonPage title="Quotations" subtitle="Backend coming in Step 8" /> },
          { path: '/sales/invoices', element: <ComingSoonPage title="Invoices" subtitle="Backend coming in Step 8" /> },
          { path: '/sales/cash-sales', element: <ComingSoonPage title="Cash Sales" subtitle="Backend coming in Step 8" /> },
          { path: '/sales/advance-receipts', element: <ComingSoonPage title="Advance Receipts" subtitle="Backend coming in Step 8" /> },
          { path: '/sales/recurring', element: <ComingSoonPage title="Recurring Invoices" subtitle="Backend coming in Step 8" /> },
          { path: '/sales/credit-notes', element: <ComingSoonPage title="Credit Notes" subtitle="Backend coming in Step 8" /> },
          { path: '/sales/payments', element: <ComingSoonPage title="Customer Payments" subtitle="Backend coming in Step 8" /> },

          // ── Purchases (all coming soon — Step 9 backend) ──
          { path: '/purchases/vendors', element: <ComingSoonPage title="Vendors" subtitle="Backend coming in Step 6" /> },
          { path: '/purchases/items', element: <ComingSoonPage title="Items" subtitle="Backend coming in Step 6.5" /> },
          { path: '/purchases/orders', element: <ComingSoonPage title="Purchase Orders" subtitle="Backend coming in Step 9" /> },
          { path: '/purchases/bills', element: <ComingSoonPage title="Bills" subtitle="Backend coming in Step 9" /> },
          { path: '/purchases/payments', element: <ComingSoonPage title="Vendor Payments" subtitle="Backend coming in Step 9" /> },
          { path: '/purchases/returns', element: <ComingSoonPage title="Purchase Returns" subtitle="Backend coming in Step 9" /> },
          { path: '/purchases/adjust-inventory', element: <ComingSoonPage title="Adjust Inventory" subtitle="Backend coming in Step 11" /> },

          // ── Expenses (Step 10 backend) ──
          { path: '/expenses', element: <ComingSoonPage title="Expenses" subtitle="Backend coming in Step 10" /> },
          { path: '/expenses/recurring', element: <ComingSoonPage title="Recurring Expenses" subtitle="Backend coming in Step 10" /> },
          { path: '/expenses/mileage', element: <ComingSoonPage title="Mileage" subtitle="Backend coming in Step 10" /> },

          // ── Banking (Step 14 backend) ──
          { path: '/banking/accounts', element: <ComingSoonPage title="Bank Accounts" subtitle="Backend coming in Step 14" /> },
          { path: '/banking/reconciliation', element: <ComingSoonPage title="Reconciliation" subtitle="Backend coming in Step 14" /> },
          { path: '/banking/transfer', element: <ComingSoonPage title="Transfer Funds" subtitle="Backend coming in Step 14" /> },

          // ── Budget (Step 13 backend) ──
          { path: '/budget', element: <ComingSoonPage title="Budget" subtitle="Backend coming in Step 13" /> },

          // ── Reports ──
          // Six are done in backend; UIs come in Phase 5n, 5o, 5p, 5q.
          { path: '/reports', element: <ComingSoonPage title="All Reports" subtitle="Coming in Phase 5n" /> },
          { path: '/reports/balance-sheet', element: <ComingSoonPage title="Balance Sheet" subtitle="Coming in Phase 5n" /> },
          { path: '/reports/profit-loss', element: <ComingSoonPage title="Profit & Loss" subtitle="Coming in Phase 5o" /> },
          { path: '/reports/cash-flow', element: <ComingSoonPage title="Cash Flow Statement" subtitle="Coming in Phase 5p" /> },
          { path: '/reports/trial-balance', element: <ComingSoonPage title="Trial Balance" subtitle="Coming in Phase 5q" /> },
          { path: '/reports/general-ledger', element: <ComingSoonPage title="General Ledger" subtitle="Coming in Phase 5q" /> },
          { path: '/reports/account-transactions', element: <ComingSoonPage title="Account Transactions" subtitle="Coming in Phase 5q" /> },
          { path: '/reports/equity', element: <ComingSoonPage title="Statement of Changes in Equity" subtitle="Backend coming in Step 12" /> },
          { path: '/reports/ratios', element: <ComingSoonPage title="Financial Ratios" subtitle="Backend coming in Step 16" /> },

          // ── Settings (from user menu) ──
          { path: '/settings', element: <ComingSoonPage title="Settings" subtitle="Coming in Phase 5s" /> },
          { path: '/settings/profile', element: <ComingSoonPage title="Profile" subtitle="Coming in Phase 5s" /> },

          // ── Help & About (from user menu) ──
          { path: '/help', element: <ComingSoonPage title="Help & Documentation" subtitle="Coming soon" /> },
          { path: '/about', element: <ComingSoonPage title="About Nidus ERP" subtitle="Coming soon" /> },
        ],
      },
    ],
  },

  // ══════════════════════════════════════════════════
  // ROOT REDIRECT + CATCH-ALL
  // ══════════════════════════════════════════════════
  { path: '/', element: <Navigate to="/dashboard" replace /> },
  { path: '*', element: <NotFoundPage /> },
]);