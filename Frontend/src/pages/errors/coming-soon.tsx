// frontend/src/pages/errors/coming-soon.tsx
//
// Reusable "Coming Soon" placeholder.
// Now renders INSIDE AppShellLayout — no sidebar/topbar/full-screen layout
// (the shell provides those).

import { Link } from 'react-router-dom';
import { Construction } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ComingSoonPageProps {
  title: string;
  subtitle?: string;
}

export function ComingSoonPage({ title, subtitle }: ComingSoonPageProps) {
  return (
    // Centered within the content area provided by the shell.
    // py-16 = generous vertical breathing room without taking the full viewport.
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="text-center max-w-md">
        <div className="mx-auto h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center">
          <Construction className="h-6 w-6 text-primary" />
        </div>
        <p className="mt-4 text-sm font-medium text-primary">Coming Soon</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">{title}</h1>
        {subtitle && (
          <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
        )}
        <div className="mt-6">
          <Button variant="outline" asChild>
            <Link to="/dashboard">Back to dashboard</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}