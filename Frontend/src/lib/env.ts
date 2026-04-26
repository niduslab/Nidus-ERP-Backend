// frontend/src/lib/env.ts
//
// Centralized environment variable access.
//
// WHY THIS FILE EXISTS:
//   Vite exposes env vars to the frontend via import.meta.env, but ONLY
//   if they're prefixed VITE_ (security: prevents accidentally leaking
//   server-side secrets to the browser). Centralizing access here means:
//     1. Typos get caught at compile time
//     2. Defaults are obvious (the `??` fallbacks below)
//     3. Future you searches one file when migrating env management
//
// HOW TO ADD A NEW ENV VAR:
//   1. Create/edit frontend/.env.local with: VITE_MY_VAR=value
//   2. Add it here as: export const MY_VAR = import.meta.env.VITE_MY_VAR ?? 'default'
//   3. Restart Vite (env vars only load on dev-server start)

// ── API base URL ──
// Default points to the local Django dev server. To override (e.g., for
// staging deploys), create frontend/.env.local with:
//   VITE_API_BASE_URL=https://api-staging.nidus-erp.com
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

// ── App name (for browser tab title, footer, etc.) ──
export const APP_NAME = 'Nidus ERP';

// ── Debug flag — true in dev, false in production builds. ──
// Vite sets import.meta.env.DEV automatically based on the build mode.
// Use this to enable noisy console logs only in development.
export const IS_DEV = import.meta.env.DEV;