// frontend/src/components/layout/app-shell-layout.tsx
//
// THE APP SHELL — persistent layout for every authenticated page.
//
// STRUCTURE:
//   ┌──────────────────────────────────────────────────┐
//   │ Sidebar │ Topbar                                 │
//   │         ├────────────────────────────────────────┤
//   │         │                                        │
//   │  nav    │  <Outlet /> — current route renders    │
//   │  links  │  here (Dashboard, CoA, Journals, etc.) │
//   │         │                                        │
//   │         │                                        │
//   └──────────────────────────────────────────────────┘
//
// USAGE (in router.tsx):
//   {
//     element: <ProtectedRoute />,
//     children: [
//       {
//         element: <AppShellLayout />,
//         children: [
//           { path: '/dashboard', element: <DashboardPage /> },
//           { path: '/coa', element: <CoAPage /> },
//           ...
//         ],
//       },
//     ],
//   }

import { Outlet } from 'react-router-dom';
import { Sidebar } from './sidebar';
import { Topbar } from './topbar';

export function AppShellLayout() {
  return (
    // h-screen = exactly viewport height (no body scroll)
    // flex = sidebar + main area side by side
    // overflow-hidden on the wrapper = no double scrollbars
    <div className="flex h-screen overflow-hidden bg-background text-foreground">

      {/* ── Sidebar: takes its own width via the layout component ── */}
      <Sidebar />

      {/* ── Main area: topbar + scrollable content ── */}
      {/* min-w-0 = critical fix for flex children that contain scrollable
          content. Without it, content with long unbreakable strings (long
          URLs, code blocks) can blow out the flex container's width. */}
      <div className="flex flex-1 flex-col min-w-0">

        <Topbar />

        {/* ── Scrollable content area ── */}
        {/* flex-1 = fill remaining vertical space below topbar
            overflow-y-auto = scroll only the content, not the topbar */}
        <main className="flex-1 overflow-y-auto">
          {/* Outlet renders the matched child route. Wrapped in a div with
              consistent padding so every page doesn't have to re-do it. */}
          <div className="p-4 sm:p-6 lg:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}