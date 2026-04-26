// frontend/src/api/auth.ts
//
// Typed wrapper functions for every authentication endpoint.
//
// WHY WRAPPERS INSTEAD OF apiClient.post() everywhere:
//   1. TypeScript autocomplete on parameters
//   2. Single place to change endpoint URLs (backend rename → 1 file edit)
//   3. Component code reads as `api.auth.login(...)` instead of
//      `apiClient.post('/api/auth/login/', { email, password })`

import { apiClient } from './client';

// ── Type definitions ──
// We hand-type these for now. Once your /api/schema/ matures, we could
// import from '@/types/api' instead — but the auth shapes are simple
// enough that hand-typing is faster.

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  data: {
    user: {
      id: string;
      email: string;
      full_name: string;
      is_email_verified: boolean;
    };
    tokens: {
      access: string;
      refresh: string;
    };
  };
}

export interface RegisterRequest {
  email: string;
  full_name: string;
  password: string;
  password_confirm: string;
  phone?: string;
}

// ── Endpoint wrappers ──
// All use apiClient (our configured Axios instance). Each returns the
// typed response data — callers don't deal with axios response objects.

export const authApi = {
  /** POST /api/auth/login/ */
  login: async (payload: LoginRequest): Promise<LoginResponse> => {
    const { data } = await apiClient.post<LoginResponse>(
      '/api/auth/login/',
      payload,
    );
    return data;
  },

  /** POST /api/auth/register/ */
  register: async (payload: RegisterRequest) => {
    const { data } = await apiClient.post('/api/auth/register/', payload);
    return data;
  },

  /** POST /api/auth/verify-email/ */
  verifyEmail: async (payload: { email: string; otp_code: string }) => {
    const { data } = await apiClient.post('/api/auth/verify-email/', payload);
    return data;
  },

  /** POST /api/auth/resend-otp/ */
  resendOtp: async (payload: { email: string }) => {
    const { data } = await apiClient.post('/api/auth/resend-otp/', payload);
    return data;
  },

  /** POST /api/auth/forgot-password/ */
  forgotPassword: async (payload: { email: string }) => {
    const { data } = await apiClient.post('/api/auth/forgot-password/', payload);
    return data;
  },

  /** POST /api/auth/reset-password/ */
  resetPassword: async (payload: {
    email: string;
    otp_code: string;
    new_password: string;
    new_password_confirm: string;
  }) => {
    const { data } = await apiClient.post('/api/auth/reset-password/', payload);
    return data;
  },

  /** POST /api/auth/logout/ — backend blacklists the refresh token */
  logout: async (refreshToken: string) => {
    const { data } = await apiClient.post('/api/auth/logout/', {
      refresh: refreshToken,
    });
    return data;
  },

  /** GET /api/auth/profile/ */
  getProfile: async () => {
    const { data } = await apiClient.get('/api/auth/profile/');
    return data;
  },
};