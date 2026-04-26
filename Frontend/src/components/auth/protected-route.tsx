// frontend/src/components/auth/protected-route.tsx
//
// A wrapper component that gates child routes behind authentication.
//
// USAGE (in your route config):
//   {
//     element: <ProtectedRoute />,
//     children: [
//       { path: '/dashboard', element: <DashboardPage /> },
//       { path: '/journals', element: <JournalListPage /> },
//     ],
//   }
//
// HOW IT WORKS:
//   1. Reads `isAuthenticated()` from Zustand on every render.
//   2. If unauthenticated → <Navigate to="/login" />.
//   3. If authenticated → renders <Outlet /> (the actual matched child route).
//
// WHY <Navigate> AND NOT useEffect + navigate():
//   <Navigate> is React Router's idiomatic way to redirect during render.
//   useEffect would briefly render the protected page before redirecting,
//   showing a flash of content the unauthed user shouldn't see.

import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/auth-store';

// We need a directory for this. Create it now if it doesn't exist:
//   New-Item -ItemType Directory -Force -Path src\components\auth

export function ProtectedRoute() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const location = useLocation();

  if (!isAuthenticated) {
    // ── The "redirect-after-login" pattern ──
    // We pass the current location as state. The login page will read
    // this and redirect back here after successful login.
    // E.g., user types /journals → bounces to /login → after login,
    // returns to /journals automatically.
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // <Outlet /> = "render the matched child route here."
  // This is React Router v6's nested-route mechanism.
  return <Outlet />;
}