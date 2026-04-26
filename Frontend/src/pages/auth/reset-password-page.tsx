// frontend/src/pages/auth/reset-password-page.tsx
//
// Step 2 of password reset: user enters OTP + new password.
//
// ENTRY:
//   Reached from /forgot-password via navigate('/reset-password',
//   { state: { email } }). If user lands here directly (no state),
//   we redirect to /forgot-password.
//
// AFTER SUCCESS:
//   Backend has updated the password and blacklisted ALL refresh tokens
//   for this user (forced logout on all devices). We redirect to /login
//   with a success toast — the user must sign in fresh with the new
//   password.

import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, KeyRound } from 'lucide-react';
import { toast } from 'sonner';

import { authApi } from '@/api/auth';
import { getApiErrorMessage } from '@/lib/api-error';
import { AuthLayout } from '@/pages/auth/auth-layout';
import { PasswordStrengthMeter } from '@/components/auth/password-strength-meter';

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
// Zod schema — OTP + new password + confirm
// ─────────────────────────────────────────────────────
//
// We don't include `email` in the schema because it's read from router
// state, not user input. The user never edits the email here.
const resetSchema = z
  .object({
    otp_code: z
      .string()
      .min(6, 'Enter the 6-digit code')
      .max(6, 'Code must be exactly 6 digits')
      .regex(/^\d{6}$/, 'Code must be 6 digits'),

    new_password: z
      .string()
      .min(8, 'Password must be at least 8 characters'),

    new_password_confirm: z
      .string()
      .min(1, 'Please confirm your password'),
  })
  .refine((data) => data.new_password === data.new_password_confirm, {
    message: 'Passwords do not match',
    path: ['new_password_confirm'],
  });

type ResetFormValues = z.infer<typeof resetSchema>;


export function ResetPasswordPage() {
  const location = useLocation();
  const navigate = useNavigate();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const email = (location.state as any)?.email as string | undefined;

  const [submitting, setSubmitting] = useState(false);

  const form = useForm<ResetFormValues>({
    resolver: zodResolver(resetSchema),
    defaultValues: {
      otp_code: '',
      new_password: '',
      new_password_confirm: '',
    },
    mode: 'onBlur',
  });

  // Live values for the strength meter
  const newPassword = form.watch('new_password');

  // Guard: if email is missing (direct visit), bounce to /forgot-password.
  if (!email) {
    return <Navigate to="/forgot-password" replace />;
  }

  async function onSubmit(values: ResetFormValues) {
    setSubmitting(true);

    try {
      await authApi.resetPassword({
        email: email!,
        otp_code: values.otp_code,
        new_password: values.new_password,
        new_password_confirm: values.new_password_confirm,
      });

      // Success! Backend has reset the password and forcibly logged out
      // all sessions (blacklisted all refresh tokens). User must sign in
      // again with the new password.
      toast.success('Password reset! Please sign in with your new password.');
      navigate('/login', { replace: true });
    } catch (err) {
      // Most common errors here: 400 invalid/expired OTP, 429 rate limit.
      // Surface as toast — field errors don't apply because the OTP isn't
      // really a "form field" in the structural sense.
      toast.error(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      {/* Header with key icon */}
      <div className="mb-8 text-center">
        <div className="mx-auto h-12 w-12 rounded-full bg-accent flex items-center justify-center">
          <KeyRound className="h-6 w-6 text-accent-foreground" />
        </div>
        <h1 className="mt-4 text-3xl font-bold tracking-tight">
          Reset your password
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Enter the code sent to{' '}
          <span className="font-medium text-foreground">{email}</span> and
          choose a new password.
        </p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">

          {/* OTP code — using a regular Input here, not the 6-box OtpInput
              component. The 6-box pattern is a UX flourish for the email-
              verify flow where OTP entry is the SINGLE thing on the page.
              On the reset page where there are also password fields, a
              standard input keeps the visual hierarchy clean and tab-order
              predictable. */}
          <FormField
            control={form.control}
            name="otp_code"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Reset code</FormLabel>
                <FormControl>
                  <Input
                    type="text"
                    inputMode="numeric"
                    placeholder="6-digit code"
                    autoComplete="one-time-code"
                    autoFocus
                    maxLength={6}
                    disabled={submitting}
                    className="font-mono tabular-nums tracking-widest"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* New password + strength meter */}
          <FormField
            control={form.control}
            name="new_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>New password</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    autoComplete="new-password"
                    disabled={submitting}
                    {...field}
                  />
                </FormControl>
                <PasswordStrengthMeter
                  password={newPassword}
                  userInputs={[email!]}
                />
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Confirm new password */}
          <FormField
            control={form.control}
            name="new_password_confirm"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Confirm new password</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    autoComplete="new-password"
                    disabled={submitting}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? 'Resetting…' : 'Reset password'}
          </Button>
        </form>
      </Form>

      <p className="mt-8 text-center text-sm text-muted-foreground">
        Didn't get a code?{' '}
        <Link
          to="/forgot-password"
          className="font-medium text-primary hover:underline"
        >
          Try again
        </Link>
      </p>
    </AuthLayout>
  );
}