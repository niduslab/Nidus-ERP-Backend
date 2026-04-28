// frontend/src/main.tsx
//
// THE APP ENTRY POINT.
// Phase 5f-1 added: TooltipProvider so tooltips work anywhere in the app.

import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'sonner';

import { ThemeProvider } from '@/components/theme/theme-provider';
import { TooltipProvider } from '@/components/ui/tooltip';
import { router } from '@/routes/router';
import { queryClient } from '@/lib/query-client';
import './index.css';


ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        {/* TooltipProvider must wrap any component using <Tooltip>.
            delayDuration sets the global default — individual <Tooltip>
            entries can override. 300ms = noticeably faster than the
            Radix default of 700ms (better for sidebar UX). */}
        <TooltipProvider delayDuration={300}>
          <RouterProvider router={router} />
          <Toaster
            position="top-right"
            richColors
            closeButton
            theme="system"
          />
          <ReactQueryDevtools initialIsOpen={false} />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>,
);