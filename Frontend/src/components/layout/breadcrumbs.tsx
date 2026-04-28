// frontend/src/components/layout/breadcrumbs.tsx
//
// Auto-generated breadcrumbs based on the current URL.
//
// EXAMPLE:
//   URL: /reports/balance-sheet
//   Renders: Home > Reports > Balance Sheet
//
// HOW IT WORKS:
//   - useLocation() gives us the current pathname
//   - We split it on '/' to get segments
//   - Each segment is mapped to a human label (via SEGMENT_LABELS table)
//   - Each segment except the last is a clickable link to its parent path
//
// EXTENDING:
//   To add custom labels for new segments, just add to SEGMENT_LABELS.
//   Anything not in the table falls back to title-casing the segment.

import { Link, useLocation } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Mapping from URL segment → display label ──
// We hand-curate the labels for the segments we know about. Anything
// missing falls back to a title-cased version of the segment (e.g.,
// 'foo-bar' becomes 'Foo Bar').
const SEGMENT_LABELS: Record<string, string> = {
  // Top-level
  dashboard: 'Home',
  coa: 'Chart of Accounts',
  journals: 'Manual Journals',
  bulk: 'Bulk Update',
  reports: 'Reports',

  // Sales
  sales: 'Sales',
  customers: 'Customers',
  quotations: 'Quotations',
  invoices: 'Invoices',
  'cash-sales': 'Cash Sales',
  'advance-receipts': 'Advance Receipts',
  recurring: 'Recurring',
  'credit-notes': 'Credit Notes',
  payments: 'Payments',

  // Purchases
  purchases: 'Purchases',
  vendors: 'Vendors',
  items: 'Items',
  orders: 'Orders',
  bills: 'Bills',
  returns: 'Returns',
  'adjust-inventory': 'Adjust Inventory',

  // Expenses
  expenses: 'Expenses',
  mileage: 'Mileage',

  // Banking
  banking: 'Banking',
  accounts: 'Accounts',
  reconciliation: 'Reconciliation',
  transfer: 'Transfer Funds',

  // Budget
  budget: 'Budget',

  // Reports
  'balance-sheet': 'Balance Sheet',
  'profit-loss': 'Profit & Loss',
  'cash-flow': 'Cash Flow',
  'trial-balance': 'Trial Balance',
  'general-ledger': 'General Ledger',
  'account-transactions': 'Account Transactions',
  equity: 'Statement of Changes in Equity',
  ratios: 'Financial Ratios',

  // Settings
  settings: 'Settings',
  profile: 'Profile',
};

/** Convert "foo-bar" / "fooBar" to "Foo Bar" — fallback for unknown segments. */
function titleCase(segment: string): string {
  return segment
    .replace(/-/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function Breadcrumbs() {
  const { pathname } = useLocation();

  // Split path into non-empty segments. '/reports/balance-sheet' →
  // ['reports', 'balance-sheet'].
  const segments = pathname.split('/').filter(Boolean);

  // /dashboard isn't a "real" breadcrumb path — it's the home, so we
  // suppress breadcrumbs entirely on the dashboard.
  if (segments.length === 0 || (segments.length === 1 && segments[0] === 'dashboard')) {
    return null;
  }

  // Build cumulative paths for each segment so we can link.
  // ['reports', 'balance-sheet'] → ['/reports', '/reports/balance-sheet']
  const crumbs = segments.map((segment, idx) => ({
    label: SEGMENT_LABELS[segment] ?? titleCase(segment),
    path: '/' + segments.slice(0, idx + 1).join('/'),
    isLast: idx === segments.length - 1,
  }));

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1 text-sm text-muted-foreground"
    >
      {/* Home icon — always points to /dashboard */}
      <Link
        to="/dashboard"
        className="flex items-center hover:text-foreground transition-colors"
        aria-label="Home"
      >
        <Home className="h-4 w-4" />
      </Link>

      {crumbs.map((crumb) => (
        <span key={crumb.path} className="flex items-center gap-1">
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/60" />
          {crumb.isLast ? (
            // Current page — not a link, styled as foreground.
            <span className="font-medium text-foreground">
              {crumb.label}
            </span>
          ) : (
            <Link
              to={crumb.path}
              className={cn(
                'hover:text-foreground transition-colors',
              )}
            >
              {crumb.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  );
}