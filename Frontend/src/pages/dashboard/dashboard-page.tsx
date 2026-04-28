// frontend/src/pages/dashboard/dashboard-page.tsx
//
// The dashboard home page.
//
// CONTEXT:
//   This component renders INSIDE AppShellLayout's <Outlet />, so it
//   does NOT include sidebar/topbar/headers — those are rendered by
//   the shell. This component focuses purely on the dashboard's content.
//
// CURRENT STATE: minimal welcome screen with placeholder cards.
// PHASE 5g+ will replace these cards with real data: pinned reports,
// recent journals, quick actions, etc.

import { useAuthStore } from '@/stores/auth-store';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  BookOpen,
  FileText,
  BarChart3,
  TrendingUp,
} from 'lucide-react';
import { Link } from 'react-router-dom';

export function DashboardPage() {
  const user = useAuthStore((state) => state.user);

  // First name only — friendlier greeting than full name.
  const firstName = user?.full_name?.split(' ')[0] ?? 'there';

  return (
    <div className="space-y-6">

      {/* ── Welcome header ── */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Welcome back, {firstName}
        </h1>
        <p className="mt-1 text-muted-foreground">
          Here's an overview of your accounting workspace.
        </p>
      </div>

      {/* ── Quick action cards ──
          Grid: 1 col on mobile, 2 on tablet, 4 on desktop. */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <QuickActionCard
          icon={<BookOpen className="h-5 w-5" />}
          title="Chart of Accounts"
          description="View and manage your accounts"
          to="/coa"
        />
        <QuickActionCard
          icon={<FileText className="h-5 w-5" />}
          title="New Journal"
          description="Record a manual entry"
          to="/journals"
        />
        <QuickActionCard
          icon={<BarChart3 className="h-5 w-5" />}
          title="Reports"
          description="Balance Sheet, P&L, Cash Flow"
          to="/reports"
        />
        <QuickActionCard
          icon={<TrendingUp className="h-5 w-5" />}
          title="Trial Balance"
          description="Check your books balance"
          to="/reports/trial-balance"
        />
      </div>

      {/* ── Recent activity card (placeholder) ── */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>
            Recent journals, exports, and account changes will appear here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No activity yet. Start by creating your first journal entry.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ── QuickActionCard sub-component ──
// A card that wraps a Link, with hover-lift effect.
interface QuickActionCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  to: string;
}

function QuickActionCard({ icon, title, description, to }: QuickActionCardProps) {
  return (
    <Link to={to}>
      <Card className="h-full transition-colors hover:bg-accent/50 hover:border-primary/30 cursor-pointer">
        <CardHeader className="space-y-1">
          {/* Icon in a tinted square */}
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent text-accent-foreground">
            {icon}
          </div>
          <CardTitle className="pt-2 text-base">{title}</CardTitle>
          <CardDescription className="text-xs">{description}</CardDescription>
        </CardHeader>
      </Card>
    </Link>
  );
}