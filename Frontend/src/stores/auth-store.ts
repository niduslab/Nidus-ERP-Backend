// frontend/src/stores/auth-store.ts
//
// ════════════════════════════════════════════════════════════════
//   AUTH STORE — global state for the current logged-in user
// ════════════════════════════════════════════════════════════════
//
// MENTAL MODEL:
//   A Zustand store is just a JavaScript object that React components
//   can subscribe to. When the object changes, subscribed components
//   automatically re-render. That's the entire mental model.
//
// USAGE FROM A COMPONENT:
//   const user = useAuthStore((state) => state.user);
//   const setAuth = useAuthStore((state) => state.setAuth);
//   ...
//   setAuth({ user: { id: '...', email: '...' }, accessToken: '...', refreshToken: '...' });
//
// WHY ZUSTAND OVER REDUX:
//   - 5 lines per slice instead of 50
//   - No Provider wrapping needed (works anywhere)
//   - Selector pattern same as Redux Toolkit's useSelector
//   - Persistence middleware = automatic localStorage sync
//
// WHAT GOES IN THIS STORE:
//   ONLY the bare minimum — current user identity + tokens. Everything
//   else (companies list, journals, accounts) lives in TanStack Query.
//   Don't pollute Zustand with server data — that's TanStack Query's job.

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

// ── Type definitions ──

/**
 * The minimal user identity fields we need globally.
 * Full user profile data lives in a TanStack Query cache, not here.
 */
export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  is_email_verified: boolean;
}

/**
 * What the store exposes — both data and actions.
 */
interface AuthState {
  // ── Data ──
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;

  // ── Computed ──
  // Derived state (a getter would also work, but a function is clearer
  // when it's read inside conditionals).
  isAuthenticated: () => boolean;

  // ── Actions ──
  /** Called after a successful login or token refresh. */
  setAuth: (payload: {
    user: AuthUser;
    accessToken: string;
    refreshToken: string;
  }) => void;

  /** Called after a successful access-token refresh (user unchanged). */
  setTokens: (tokens: { accessToken: string; refreshToken: string }) => void;

  /** Called on logout, on 401-after-refresh-failure, or session expiry. */
  clearAuth: () => void;
}

// ── The store ──
//
// `create()` accepts a function that receives a `set` mutator and returns
// the initial state object. The `persist` middleware wraps it to mirror
// the state to localStorage automatically on every change.
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // ── Initial state ──
      // null = not logged in. After hydration from localStorage (if a
      // session exists), these get populated.
      user: null,
      accessToken: null,
      refreshToken: null,

      // ── Computed ──
      // Returns true only when we have ALL three: user + both tokens.
      // Defensive — if any one is missing, treat the user as logged out.
      isAuthenticated: () => {
        const { user, accessToken, refreshToken } = get();
        return Boolean(user && accessToken && refreshToken);
      },

      // ── Actions ──
      // `set()` triggers a re-render in every component subscribed to
      // the changed slice. Other components are not re-rendered (Zustand's
      // selector pattern handles this efficiently).

      setAuth: ({ user, accessToken, refreshToken }) =>
        set({ user, accessToken, refreshToken }),

      setTokens: ({ accessToken, refreshToken }) =>
        set({ accessToken, refreshToken }),

      clearAuth: () =>
        set({ user: null, accessToken: null, refreshToken: null }),
    }),
    {
      // ── persist middleware config ──
      //
      // 'name' = the localStorage key. Should be unique per app to avoid
      // collisions if you run multiple apps on the same domain.
      name: 'nidus-auth',

      // 'storage' = where to persist. createJSONStorage(() => localStorage)
      // is the standard. Could also be sessionStorage (clears on tab close).
      storage: createJSONStorage(() => localStorage),

      // 'partialize' = only persist these fields. We skip computed
      // functions (isAuthenticated isn't serializable).
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    },
  ),
);