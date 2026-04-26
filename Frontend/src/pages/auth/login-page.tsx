// frontend/src/pages/auth/login-page.tsx
//
// The real login page — replaces login-placeholder.tsx from Phase 5b.
//
// FEATURES:
//   - React Hook Form + Zod validation
//   - Shows field-level errors instantly (after first blur)
//   - Disables submit while invalid OR while submitting
//   - Loading spinner inside button during submit
//   - Smart error routing: 401 → toast, 403 unverified → redirect to verify page,
//     429 → friendly rate-limit message
//   - "Forgot password?" and "Register" links (placeholder routes for now)
//   - Mobile-responsive via AuthLayout

import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { AxiosError } from 'axios';

import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/auth-store';
import { getApiErrorMessage } from '@/lib/api-error';
import { AuthLayout } from '@/pages/auth/auth-layout';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';

// ─────────────────────────────────────────────────────
// 1. ZOD SCHEMA — single source of truth for valid input
// ─────────────────────────────────────────────────────
//
// Each field has its own validation rules. The error messages here are
// what users see when validation fails (e.g., when they tab out of an
// empty email field).
const loginSchema = z.object({
  email: z
    .string()
    .min(1, 'Email is required')
    .email('Please enter a valid email address'),
  password: z
    .string()
    .min(1, 'Password is required'),
});

// `z.infer` extracts the TypeScript type from the schema.
// LoginFormValues = { email: string; password: string }
// We use this type below to give RHF strong typing.
type LoginFormValues = z.infer<typeof loginSchema>;


export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useAuthStore((state) => state.setAuth);

  // Local state for the loading spinner. Could live inside RHF's
  // `formState.isSubmitting`, but a separate flag gives clearer semantics
  // when we want to disable the button slightly longer than the actual
  // network call (e.g., during the post-success redirect).
  const [submitting, setSubmitting] = useState(false);

  // ─────────────────────────────────────────────────────
  // 2. INITIALIZE THE FORM
  // ─────────────────────────────────────────────────────
  //
  // useForm() returns a `form` object with:
  //   - form.control: passed to <FormField>
  //   - form.handleSubmit(fn): wraps your submit fn to run validation first
  //   - form.formState: { errors, isValid, isDirty, ... }
  //   - form.setError(field, { message }): manually mark a field invalid
  //
  // The `resolver` integrates Zod — RHF will call our schema's parse()
  // automatically before invoking the submit handler.
  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    // Initial values. Important: every field in the schema must have an
    // initial value to keep React's "controlled vs uncontrolled" warning
    // from firing.
    defaultValues: {
      email: '',
      password: '',
    },
    // mode='onBlur' = run validation when the user tabs out of a field
    //                 (less aggressive than 'onChange' — feels more polite)
    mode: 'onBlur',
  });

  // ─────────────────────────────────────────────────────
  // 3. SUBMIT HANDLER
  // ─────────────────────────────────────────────────────
  //
  // This function is called by form.handleSubmit() ONLY if Zod validation
  // passes. If validation fails, RHF shows errors automatically and this
  // function never runs.
  //
  // The `values` arg is fully typed (LoginFormValues) — TypeScript knows
  // values.email is a string, values.password is a string.
  async function onSubmit(values: LoginFormValues) {
    setSubmitting(true);

    try {
      // Call the backend
      const response = await authApi.login(values);

      // Persist auth state to Zustand + localStorage
      setAuth({
        user: response.data.user,
        accessToken: response.data.tokens.access,
        refreshToken: response.data.tokens.refresh,
      });

      // Friendly success toast
      toast.success(`Welcome back, ${response.data.user.full_name.split(' ')[0]}!`);

      // Redirect to wherever the user was trying to go before login,
      // or /dashboard as default.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const from = (location.state as any)?.from?.pathname ?? '/dashboard';
      navigate(from, { replace: true });
    } catch (err) {
      // ── Smart error routing ──
      // The backend returns specific status codes for different failure
      // modes. We route each to the most helpful UI response.

      if (err instanceof AxiosError && err.response?.status === 403) {
        // 403 with requires_verification = unverified email account.
        // The backend re-sent a fresh OTP automatically — redirect to
        // /verify-email so the user can complete verification.
        const data = err.response.data as {
          requires_verification?: boolean;
          email?: string;
          message?: string;
        };
        if (data?.requires_verification) {
          toast.info(
            data.message || 'Your email is not verified. Check your inbox for a new code.',
          );
          navigate('/verify-email', {
            replace: true,
            state: { email: data.email || values.email },
          });
          return;
        }
        // Other 403 = deactivated account.
        toast.error('This account has been deactivated. Contact your administrator.');
        return;
      }

      // 401 (wrong creds), 429 (rate limit), 500, network error etc.
      // → all surface as a single toast.
      toast.error(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  // ─────────────────────────────────────────────────────
  // 4. RENDER
  // ─────────────────────────────────────────────────────
  return (
    <AuthLayout>
      {/* Form heading */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Sign in</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Enter your credentials to access your account.
        </p>
      </div>

      {/* The form. Form (capital F) provides RHF context. */}
      <Form {...form}>
        {/* form.handleSubmit(onSubmit) wraps our submit handler with Zod validation */}
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">

          {/* ── Email field ── */}
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    placeholder="you@company.com"
                    autoComplete="email"
                    autoFocus     // Place keyboard cursor here on page load
                    disabled={submitting}
                    {...field}    // spreads value, onChange, onBlur, name, ref
                  />
                </FormControl>
                <FormMessage />   {/* Shows validation error if email is invalid */}
              </FormItem>
            )}
          />

          {/* ── Password field with "Forgot?" link aligned to the label ── */}
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                {/* Custom label row — label on left, "Forgot?" link on right */}
                <div className="flex items-center justify-between">
                  <FormLabel>Password</FormLabel>
                  <Link
                    to="/forgot-password"
                    className="text-sm font-medium text-primary hover:underline"
                  >
                    Forgot?
                  </Link>
                </div>
                <FormControl>
                  <Input
                    type="password"
                    autoComplete="current-password"
                    disabled={submitting}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* ── Submit button ──
              w-full = full width
              Disabled while submitting OR while form has validation errors
              the !form.formState.isValid is commented out — we want the button
              clickable so users learn what to fix when they click. */}
          <Button
            type="submit"
            className="w-full"
            disabled={submitting}
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      </Form>

      {/* Footer: register link */}
      <p className="mt-8 text-center text-sm text-muted-foreground">
        Don't have an account?{' '}
        <Link
          to="/register"
          className="font-medium text-primary hover:underline"
        >
          Create one
        </Link>
      </p>
    </AuthLayout>
  );
}