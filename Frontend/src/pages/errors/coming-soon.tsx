// frontend/src/pages/errors/coming-soon.tsx
//
// Reusable "Coming Soon" placeholder page.
// Used for sidebar items and routes whose backend / frontend aren't built yet.
//
// USAGE:
//   <ComingSoonPage title="Register" subtitle="Coming in Phase 5d" />

import { Link } from 'react-router-dom';
import { Construction } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ComingSoonPageProps {
  title: string;
  subtitle?: string;
}

export function ComingSoonPage({ title, subtitle }: ComingSoonPageProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <div className="text-center max-w-md">
        {/* Icon in a tinted square */}
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