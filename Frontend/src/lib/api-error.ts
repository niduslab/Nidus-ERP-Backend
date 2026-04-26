// frontend/src/lib/api-error.ts
//
// A helper to extract a user-friendly error message from an Axios error.
//
// PROBLEM:
//   When an API call fails, the error could be:
//     - 400 with { message: "Invalid input", errors: {...} }
//     - 401 with { message: "Invalid credentials" }
//     - 429 with no body (rate limit hit)
//     - Network timeout (no response object at all)
//
//   Each looks structurally different. A user-facing form needs ONE
//   string to display. This helper does the extraction.
//
// USAGE:
//   try {
//     await authApi.login({...});
//   } catch (err) {
//     toast.error(getApiErrorMessage(err));
//   }

import { AxiosError } from 'axios';

/**
 * Extract a human-readable error message from any error thrown during an
 * API call. Falls back to a generic message if nothing useful is found.
 */
export function getApiErrorMessage(
  error: unknown,
  fallback = 'Something went wrong. Please try again.',
): string {
  // ── Axios errors ──
  if (error instanceof AxiosError) {
    // Rate limit (DRF Throttle returns 429)
    if (error.response?.status === 429) {
      return 'Too many attempts. Please wait a moment and try again.';
    }

    // Network timeout / DNS failure / server unreachable
    if (!error.response) {
      return 'Network error — please check your connection.';
    }

    // Backend returned a structured error
    const data = error.response.data as { message?: string } | undefined;
    if (data?.message) {
      return data.message;
    }

    // Fallback to HTTP status
    return `Request failed with status ${error.response.status}`;
  }

  // ── Standard JS errors ──
  if (error instanceof Error) {
    return error.message;
  }

  // ── Anything else (rare) ──
  return fallback;
}

/**
 * Helper for forms that get a 400 response with field-level errors.
 *
 * Backend response shape (from your DRF):
 *   { success: false, message: "Invalid input", errors: { email: ["..."] } }
 *
 * Returns an object suitable for setting on the form:
 *   { email: "..." }
 *
 * Used in catch blocks like:
 *   catch (err) {
 *     const fieldErrors = getFieldErrors(err);
 *     for (const [field, msg] of Object.entries(fieldErrors)) {
 *       form.setError(field, { message: msg });
 *     }
 *   }
 */
export function getFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof AxiosError) || !error.response) return {};

  const data = error.response.data as
    | { errors?: Record<string, string | string[]> }
    | undefined;

  if (!data?.errors) return {};

  // DRF returns string arrays per field. Take the first error of each.
  const result: Record<string, string> = {};
  for (const [field, value] of Object.entries(data.errors)) {
    if (Array.isArray(value)) {
      result[field] = value[0] ?? '';
    } else if (typeof value === 'string') {
      result[field] = value;
    }
  }
  return result;
}