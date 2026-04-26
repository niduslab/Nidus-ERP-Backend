// frontend/src/main.tsx
//
// THE APP ENTRY POINT.
// Order of providers matters — outer providers are available to inner ones.

import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Toaster } from 'sonner';

import { ThemeProvider } from '@/components/theme/theme-provider';
import { router } from '@/routes/router';
import { queryClient } from '@/lib/query-client';
import './index.css';


ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* ── ThemeProvider ──
        Outermost: every component (including toasts) needs theme access. */}
    <ThemeProvider>

      {/* ── QueryClientProvider ──
          Provides the TanStack Query cache to every useQuery / useMutation
          inside the app. Without this, those hooks throw at runtime. */}
      <QueryClientProvider client={queryClient}>

        {/* ── RouterProvider ──
            Renders the matched route based on the current URL. */}
        <RouterProvider router={router} />

        {/* ── Toaster ──
            Renders an invisible portal that displays toast notifications
            triggered anywhere in the app via toast.success(...) etc.
            position='top-right' is the de-facto pro standard. */}
        <Toaster
          position="top-right"
          richColors
          closeButton
          // theme='system' = match the user's app theme
          theme="system"
        />

        {/* ── React Query Devtools ──
            Floating panel (bottom-right) showing every cached query, its
            staleness, refetch state. INVALUABLE for debugging.
            Vite tree-shakes this out of production builds automatically
            if we wrap it (we don't yet — it's actually fine to ship in dev,
            and you can hide it via the panel itself). */}
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>,
);