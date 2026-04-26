// frontend/src/lib/query-client.ts
//
// The single QueryClient instance for the whole app.
//
// WHY EXTRACTED INTO ITS OWN FILE:
//   - Tests can import it to clear caches between test cases
//   - The QueryClient holds the cache + default options for ALL queries
//   - Having one place to tune behavior (stale times, retries) is critical

import { QueryClient } from '@tanstack/react-query';

// ── The QueryClient ──
//
// `defaultOptions` apply to every useQuery / useMutation that doesn't
// explicitly override them. Think of these as your team's defaults.
export const queryClient = new QueryClient({
  defaultOptions: {
    // ── Query defaults ──
    queries: {
      // staleTime = how long data is considered "fresh" after a successful fetch.
      // During this window, accessing the same query key returns the cache
      // INSTANTLY without a network call. Default is 0 (always stale).
      // 60 seconds is a sensible default — strikes a balance between
      // freshness and server load.
      staleTime: 60 * 1000, // 60 seconds

      // gcTime (formerly cacheTime) = how long unused query data stays in
      // memory after the last component unsubscribes. After this, it's
      // garbage collected. 5 minutes lets users navigate back without
      // re-fetching, but doesn't bloat memory forever.
      gcTime: 5 * 60 * 1000, // 5 minutes

      // retry = how many times to auto-retry a failed query before giving up.
      // 1 retry handles transient network blips; more would be annoying
      // (long delays before the user sees an error message).
      retry: 1,

      // refetchOnWindowFocus = re-fetch when user tabs back to the browser.
      // Excellent for keeping data fresh in long-running ERP workflows.
      // Some teams disable this; for an accounting app where data changes
      // matter, leaving it ON is the right default.
      refetchOnWindowFocus: true,
    },

    // ── Mutation defaults ──
    mutations: {
      // We DON'T retry mutations by default. A failed mutation might have
      // partial side effects on the server — retrying could double-create
      // a journal entry, double-charge a customer, etc. Caller should
      // explicitly opt in to retries when safe.
      retry: 0,
    },
  },
});