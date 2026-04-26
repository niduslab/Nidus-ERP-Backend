// frontend/src/api/client.ts
//
// ════════════════════════════════════════════════════════════════════
//   AXIOS CLIENT WITH JWT AUTO-REFRESH
// ════════════════════════════════════════════════════════════════════
//
// This is the SINGLE source of HTTP requests in the entire app. Every
// API call goes through this configured Axios instance.
//
// THREE THINGS IT DOES:
//   1. Attaches the access token to every request automatically
//   2. On 401 response: tries to refresh the access token, then retries
//   3. On refresh failure: clears auth state, redirects to /login
//
// WHY ONE INSTANCE INSTEAD OF axios.get() everywhere:
//   - Centralizes baseURL config (change in one place for staging/prod)
//   - Centralizes the auth header logic (no copy-paste of "Bearer ${token}")
//   - Lets us add interceptors that apply to ALL requests
//
// THE INTERCEPTOR ARCHITECTURE:
//   Axios supports two types of interceptors:
//     - Request interceptors: modify the request before it goes out
//     - Response interceptors: modify the response (or handle errors)
//   We use one of each. They're chained automatically.

import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/auth-store';
import { API_BASE_URL } from '@/lib/env';

// ── Create the configured axios instance ──
//
// We DON'T export the raw axios — we export only this configured client.
// This guarantees every request goes through our interceptors.
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // 30-second default timeout. Reports can be slow but anything past 30s
  // is almost certainly a network problem worth surfacing.
  timeout: 30000,
});


// ════════════════════════════════════════════════════════════════════
//   REQUEST INTERCEPTOR — attach access token
// ════════════════════════════════════════════════════════════════════
//
// Runs on EVERY outgoing request before it leaves the browser.
// Reads the current access token from Zustand and attaches it as
// `Authorization: Bearer <token>`.

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // useAuthStore.getState() = read the store WITHOUT subscribing.
    // (We can't use the React hook here — interceptors aren't components.)
    const accessToken = useAuthStore.getState().accessToken;

    // Only add the header if we have a token.
    // Anonymous endpoints (/login/, /register/) work fine without it.
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }

    return config;
  },
  (error) => {
    // Request setup itself failed (rare — usually a code bug).
    // Reject so the caller's .catch() handler runs.
    return Promise.reject(error);
  },
);


// ════════════════════════════════════════════════════════════════════
//   RESPONSE INTERCEPTOR — auto-refresh on 401
// ════════════════════════════════════════════════════════════════════
//
// THE ALGORITHM:
//   1. Response has status 401 (Unauthorized) → access token expired.
//   2. Check that this isn't itself a refresh request (avoid infinite loop).
//   3. Check we haven't already retried this exact request.
//   4. Call POST /api/auth/token/refresh/ with the refresh token.
//   5. On success: update the store with the new access token, retry the
//      original request with the new token.
//   6. On failure: clear auth state, redirect to /login.
//
// THE QUEUE PATTERN (subtle but critical):
//   Imagine 3 components fire 3 requests simultaneously, and the access
//   token has just expired. All 3 get 401. Without coordination, we'd
//   call /token/refresh/ 3 times in parallel — wasted requests AND a
//   potential race condition where the first refresh's new token gets
//   blacklisted by the second refresh.
//
//   Solution: a single in-flight refresh promise. The first 401 starts
//   the refresh. The 2nd and 3rd 401s `await` that same promise. When
//   it resolves, all three retry with the new token.

// In-flight refresh state (module-level — shared across all interceptor calls).
let refreshPromise: Promise<string> | null = null;

apiClient.interceptors.response.use(
  // ── On success: pass through unchanged ──
  (response) => response,

  // ── On error: try to handle 401 specifically ──
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;  // Custom flag we add to detect retried requests
    };

    // ── Bail-out conditions ──
    // Not a 401? → pass the error through to the caller's .catch().
    if (error.response?.status !== 401) {
      return Promise.reject(error);
    }

    // No request config? → can't retry. Pass through.
    if (!originalRequest) {
      return Promise.reject(error);
    }

    // The 401 came from an endpoint that should NEVER trigger refresh:
    //   - /api/auth/login/  → 401 means "wrong credentials" (real, surface it)
    //   - /api/auth/token/refresh/ → already trying to refresh, can't loop
    // For these, pass the original error to the caller without touching auth.
    const noRefreshPaths = [
      '/api/auth/login/',
      '/api/auth/token/refresh/',
    ];
    if (originalRequest.url && noRefreshPaths.some((p) => originalRequest.url!.includes(p))) {
      // For login: don't clear auth (user wasn't authed anyway).
      // For refresh: refresh token is bad → clear auth so ProtectedRoute redirects.
      if (originalRequest.url.includes('/api/auth/token/refresh/')) {
        handleAuthFailure();
      }
      return Promise.reject(error);
    }

    // Already retried this request once? → don't loop forever.
    if (originalRequest._retry) {
      handleAuthFailure();
      return Promise.reject(error);
    }

    // Mark this request as "we are retrying you" so the next 401 doesn't
    // try to refresh again.
    originalRequest._retry = true;

    // ── Begin the queue logic ──
    // If a refresh is already in flight, wait for it.
    // If not, start one — and store the promise so concurrent 401s can wait too.
    try {
      const newAccessToken = await getOrCreateRefreshPromise();

      // Refresh succeeded! Update the original request's auth header
      // and re-issue the request.
      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
      }
      return apiClient(originalRequest);
    } catch (refreshError) {
      // Refresh failed (refresh token expired, network error, etc.)
      // Force logout and reject with the original 401.
      handleAuthFailure();
      return Promise.reject(refreshError);
    }
  },
);


// ════════════════════════════════════════════════════════════════════
//   HELPER — single-flight refresh promise
// ════════════════════════════════════════════════════════════════════

/**
 * Returns the in-flight refresh promise (creating it if needed).
 *
 * This is the "single-flight" pattern: only ONE refresh request is in
 * flight at a time, even if many original requests get 401 simultaneously.
 */
function getOrCreateRefreshPromise(): Promise<string> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    const refreshToken = useAuthStore.getState().refreshToken;
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      // ── Call the refresh endpoint ──
      // Use raw axios.post (NOT apiClient.post) to skip our own
      // interceptors — otherwise we'd recursively try to refresh
      // when refreshing.
      const response = await axios.post<{ access: string; refresh: string }>(
        `${API_BASE_URL}/api/auth/token/refresh/`,
        { refresh: refreshToken },
        { headers: { 'Content-Type': 'application/json' } },
      );

      const { access, refresh } = response.data;

      // Update the store with the new token pair.
      // (SimpleJWT with rotation issues a fresh refresh token each time.)
      useAuthStore.getState().setTokens({
        accessToken: access,
        refreshToken: refresh,
      });

      return access;
    } finally {
      // Always clear the promise so the NEXT 401 starts a fresh refresh.
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Called when authentication has definitively failed:
 *   - Refresh token is invalid/expired
 *   - Refresh endpoint returned 401
 *   - Refresh succeeded but the retried request still 401'd
 *
 * Clears the auth store. The router's <ProtectedRoute> will detect the
 * cleared state on the next render and redirect to /login.
 *
 * NOTE: We don't use react-router's navigate() here because this code
 * runs OUTSIDE React. We rely on Zustand's reactivity: when the store
 * changes, every subscribed component re-renders, and the
 * <ProtectedRoute> wrapper handles the redirect.
 */
function handleAuthFailure(): void {
  useAuthStore.getState().clearAuth();
}