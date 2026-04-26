// frontend/src/pages/auth/auth-layout.tsx
//
// Shared layout for all authentication pages (login, register, forgot/reset).
//
// LAYOUT:
//   ┌──────────────────────┬──────────────────────────────┐
//   │  BRAND PANEL (left)  │   FORM (right)               │
//   │                      │                              │
//   │  - Logo              │   - Page title               │
//   │  - Tagline           │   - Form                     │
//   │  - Marketing copy    │   - Submit button            │
//   │  - Feature points    │   - Footer link              │
//   │                      │                              │
//   │  (hidden on mobile)  │   (full width on mobile)     │
//   └──────────────────────┴──────────────────────────────┘
//
// USAGE:
//   <AuthLayout>
//     <YourPageContent />
//   </AuthLayout>
//
// The layout takes care of the brand panel + responsive behavior.
// Each auth page only needs to render its form on the right.

import type { ReactNode } from 'react';
import { ShieldCheck, BarChart3, BookOpen } from 'lucide-react';
import { ThemeToggle } from '@/components/theme/theme-toggle';

interface AuthLayoutProps {
  children: ReactNode;
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    // min-h-screen = full viewport height minimum
    // grid lg:grid-cols-2 = single column on mobile, two columns on desktop (≥1024px)
    <div className="min-h-screen grid lg:grid-cols-2">

      {/* ── LEFT: Brand panel ── */}
      {/* hidden lg:flex = hidden below 1024px, shown as flex column above */}
      {/* bg-primary = teal background using your brand color */}
      {/* text-primary-foreground = white text */}
      <aside className="hidden lg:flex flex-col justify-between bg-primary p-12 text-primary-foreground">

        {/* Top: logo + name */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-md bg-primary-foreground/20 flex items-center justify-center font-bold">
            N
          </div>
          <span className="text-xl font-semibold tracking-tight">Nidus ERP</span>
        </div>

        {/* Middle: marketing message */}
        <div className="space-y-6 max-w-md">
          <h2 className="text-4xl font-bold tracking-tight leading-tight">
            Financial clarity for Bangladesh businesses.
          </h2>
          <p className="text-lg text-primary-foreground/80">
            Multi-tenant ERP. IFRS-compliant double-entry. Built for accountants,
            auditors, and the businesses that depend on them.
          </p>

          {/* Feature bullets */}
          <ul className="space-y-3 pt-4">
            <FeatureBullet icon={<BookOpen className="h-4 w-4" />}>
              Double-entry, every transaction balances
            </FeatureBullet>
            <FeatureBullet icon={<BarChart3 className="h-4 w-4" />}>
              6 financial reports, IFRS-compliant
            </FeatureBullet>
            <FeatureBullet icon={<ShieldCheck className="h-4 w-4" />}>
              137 automated tests, audit-ready
            </FeatureBullet>
          </ul>
        </div>

        {/* Bottom: small copyright */}
        <p className="text-sm text-primary-foreground/60">
          © 2026 Nidus ERP — Built for Bangladesh
        </p>
      </aside>

      {/* ── RIGHT: Form panel ── */}
      {/* relative = needed for absolute-positioned theme toggle */}
      <main className="relative flex flex-col items-center justify-center bg-background p-6 sm:p-12">

        {/* Theme toggle (top-right corner) */}
        <div className="absolute top-4 right-4">
          <ThemeToggle />
        </div>

        {/* Mobile-only logo (since brand panel is hidden) */}
        <div className="lg:hidden mb-8 flex items-center gap-2">
          <div className="h-8 w-8 rounded-md bg-primary flex items-center justify-center">
            <span className="text-primary-foreground font-bold text-sm">N</span>
          </div>
          <span className="text-lg font-semibold tracking-tight">Nidus ERP</span>
        </div>

        {/* The actual page form. max-w-md keeps it readable on wide screens. */}
        <div className="w-full max-w-md">
          {children}
        </div>
      </main>
    </div>
  );
}

// ── Tiny helper component for the feature bullets ──
function FeatureBullet({
  icon,
  children,
}: {
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <li className="flex items-center gap-3 text-sm">
      <span className="h-7 w-7 rounded-md bg-primary-foreground/15 flex items-center justify-center flex-shrink-0">
        {icon}
      </span>
      <span className="text-primary-foreground/90">{children}</span>
    </li>
  );
}