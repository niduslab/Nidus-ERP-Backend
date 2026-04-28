// frontend/src/components/layout/sidebar-config.ts
//
// ════════════════════════════════════════════════════════════════
//   SIDEBAR NAVIGATION DATA
// ════════════════════════════════════════════════════════════════
//
// The single source of truth for what appears in the sidebar.
// Adding a new module or link = edit this file. The Sidebar component
// renders whatever shape this data takes — it doesn't hardcode anything.
//
// SEPARATION OF DATA AND PRESENTATION:
//   This is a data file (.ts, no JSX). The sidebar.tsx component reads
//   this and renders it. Why split: easier to test the data shape,
//   easier to A/B-test variations, easier to fetch from the backend
//   later if we ever want server-driven menus.
//
// COMING-SOON BADGE:
//   `comingSoon: true` marks a link as not-yet-implemented. The renderer
//   shows a small "Soon" badge and the link is non-clickable (or routes
//   to the ComingSoonPage placeholder).

import type { LucideIcon } from 'lucide-react';
import {
  Home,
  BookOpen,
  ShoppingCart,
  Wallet,
  Receipt,
  Landmark,
  Target,
  BarChart3,
} from 'lucide-react';

/**
 * One link inside a section. May or may not have a real route yet.
 */
export interface SidebarLink {
  /** Display label shown to the user. */
  label: string;

  /**
   * URL the link navigates to. Even Coming Soon items have a route —
   * they go to the /coming-soon placeholder via router config.
   */
  to: string;

  /** Show "Soon" badge + style as muted. */
  comingSoon?: boolean;
}

/**
 * One collapsible section in the sidebar (e.g., "Sales", "Reports").
 * A section has an icon and contains 1+ links.
 */
export interface SidebarSection {
  /** Display label shown as the section header. */
  label: string;

  /** Lucide icon component shown next to the section label. */
  icon: LucideIcon;

  /**
   * Whether this section is "open" (children visible) by default.
   * Most are open. Coming Soon-heavy sections are closed by default
   * to reduce noise.
   */
  defaultOpen?: boolean;

  /** The links inside this section. */
  links: SidebarLink[];
}

/**
 * Top-level sidebar entry. Either a single link (like "Home") or a
 * section with multiple links (like "Sales").
 *
 * Discriminated union: TypeScript uses the `kind` field to know which
 * shape we have. Pattern called "tagged unions" or "sum types".
 */
export type SidebarEntry =
  | { kind: 'link'; label: string; icon: LucideIcon; to: string; comingSoon?: boolean }
  | { kind: 'section'; section: SidebarSection };


// ════════════════════════════════════════════════════════════════
//   THE NAVIGATION TREE
// ════════════════════════════════════════════════════════════════
//
// The order here is the order in the sidebar.
// `as const satisfies SidebarEntry[]` is a TS pattern that:
//   - Verifies every entry conforms to SidebarEntry shape
//   - Preserves the literal types (so 'kind' is 'link' not generic string)
//   - Makes the array readonly (can't accidentally mutate)
export const SIDEBAR_ENTRIES = [
  // ── Home (top-level link, no section) ──
  {
    kind: 'link',
    label: 'Home',
    icon: Home,
    to: '/dashboard',
  },

  // ── Accounting ──
  {
    kind: 'section',
    section: {
      label: 'Accounting',
      icon: BookOpen,
      defaultOpen: true,
      links: [
        { label: 'Chart of Accounts', to: '/coa' },
        { label: 'Manual Journals', to: '/journals' },
        { label: 'Bulk Update', to: '/journals/bulk' },
      ],
    },
  },

  // ── Sales (all coming soon for now) ──
  {
    kind: 'section',
    section: {
      label: 'Sales',
      icon: ShoppingCart,
      defaultOpen: false,
      links: [
        { label: 'Customers', to: '/sales/customers', comingSoon: true },
        { label: 'Quotations', to: '/sales/quotations', comingSoon: true },
        { label: 'Invoices', to: '/sales/invoices', comingSoon: true },
        { label: 'Cash Sales', to: '/sales/cash-sales', comingSoon: true },
        { label: 'Advance Receipts', to: '/sales/advance-receipts', comingSoon: true },
        { label: 'Recurring Invoices', to: '/sales/recurring', comingSoon: true },
        { label: 'Customer Payments', to: '/sales/payments', comingSoon: true },
        { label: 'Credit Notes', to: '/sales/credit-notes', comingSoon: true },
      ],
    },
  },

  // ── Purchases (all coming soon) ──
  {
    kind: 'section',
    section: {
      label: 'Purchases',
      icon: Wallet,
      defaultOpen: false,
      links: [
        { label: 'Vendors', to: '/purchases/vendors', comingSoon: true },
        { label: 'Items', to: '/purchases/items', comingSoon: true },
        { label: 'Purchase Orders', to: '/purchases/orders', comingSoon: true },
        { label: 'Bills', to: '/purchases/bills', comingSoon: true },
        { label: 'Vendor Payments', to: '/purchases/payments', comingSoon: true },
        { label: 'Purchase Returns', to: '/purchases/returns', comingSoon: true },
        { label: 'Adjust Inventory', to: '/purchases/adjust-inventory', comingSoon: true },
      ],
    },
  },

  // ── Expenses (coming soon) ──
  {
    kind: 'section',
    section: {
      label: 'Expenses',
      icon: Receipt,
      defaultOpen: false,
      links: [
        { label: 'Expenses', to: '/expenses', comingSoon: true },
        { label: 'Recurring Expenses', to: '/expenses/recurring', comingSoon: true },
        { label: 'Mileage', to: '/expenses/mileage', comingSoon: true },
      ],
    },
  },

  // ── Banking (coming soon) ──
  {
    kind: 'section',
    section: {
      label: 'Banking',
      icon: Landmark,
      defaultOpen: false,
      links: [
        { label: 'Bank Accounts', to: '/banking/accounts', comingSoon: true },
        { label: 'Reconciliation', to: '/banking/reconciliation', comingSoon: true },
        { label: 'Transfer Funds', to: '/banking/transfer', comingSoon: true },
      ],
    },
  },

  // ── Budget (single coming-soon link, treated as top-level) ──
  {
    kind: 'link',
    label: 'Budget',
    icon: Target,
    to: '/budget',
    comingSoon: true,
  },

  // ── Reports ──
  {
    kind: 'section',
    section: {
      label: 'Reports',
      icon: BarChart3,
      defaultOpen: true,
      links: [
        { label: 'Balance Sheet', to: '/reports/balance-sheet' },
        { label: 'Profit & Loss', to: '/reports/profit-loss' },
        { label: 'Cash Flow Statement', to: '/reports/cash-flow' },
        { label: 'Trial Balance', to: '/reports/trial-balance' },
        { label: 'General Ledger', to: '/reports/general-ledger' },
        { label: 'Account Transactions', to: '/reports/account-transactions' },
        { label: 'Changes in Equity', to: '/reports/equity', comingSoon: true },
        { label: 'Financial Ratios', to: '/reports/ratios', comingSoon: true },
        { label: 'All Reports', to: '/reports' },
      ],
    },
  },
] as const satisfies readonly SidebarEntry[];