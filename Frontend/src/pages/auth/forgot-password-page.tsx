// frontend/src/pages/auth/forgot-password-page.tsx
//
// Step 1 of password reset: user types their email, we send them a code.
//
// SECURITY NOTE:
//   The backend's /api/auth/forgot-password/ endpoint always returns 200
//   with the same message regardless of whether the email exists. This
//   prevents email enumeration. Our frontend mirrors this — we always
//   show the same success screen. Don't try to be clever and surface a
//   "no account found" error.

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, MailCheck } from 'lucide-react';
import { toast } from 'sonner';

import { authApi } from '@/api/auth';
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
// Zod schema — just an email field
// ─────────────────────────────────────────────────────
const forgotSchema = z.object({
  email: z
    .string()
    .min(1, 'Email is required')
    .email('Please enter a valid email address'),
});

type ForgotFormValues = z.infer<typeof forgotSchema>;


export function ForgotPasswordPage() {
  const navigate = useNavigate();

  // Two-state UI: form OR confirmation screen.
  // sentToEmail !== null means "we just sent the code — show confirmation".
  // This avoids needing two separate routes for the two states.
  const [sentToEmail, setSentToEmail] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<ForgotFormValues>({
    resolver: zodResolver(forgotSchema),
    defaultValues: { email: '' },
    mode: 'onBlur',
  });

  async function onSubmit(values: ForgotFormValues) {
    setSubmitting(true);

    try {
      // Backend always returns 200 here — but we still wrap in try/catch
      // for genuine network errors / 429 rate-limit responses.
      await authApi.forgotPassword({ email: values.email });

      // Show the confirmation screen with the email displayed.
      setSentToEmail(values.email);
    } catch (err) {
      // Most likely a 429 rate-limit. Surface as toast.
      toast.error(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  // ── Confirmation screen ──
  // Shown after the user submits. Includes a CTA to proceed to /reset-password.
  if (sentToEmail) {
    return (
      <AuthLayout>
        <div className="text-center">
          <div className="mx-auto h-12 w-12 rounded-full bg-accent flex items-center justify-center">
            <MailCheck className="h-6 w-6 text-accent-foreground" />
          </div>

          <h1 className="mt-4 text-3xl font-bold tracking-tight">
            Check your email
          </h1>

          <p className="mt-2 text-sm text-muted-foreground">
            If an account exists for{' '}
            <span className="font-medium text-foreground">{sentToEmail}</span>,
            we've sent a 6-digit reset code.
          </p>

          <p className="mt-1 text-sm text-muted-foreground">
            The code expires in 10 minutes.
          </p>

          {/* ── Primary CTA: navigate to /reset-password with email in state ── */}
          <Button
            className="mt-6 w-full"
            onClick={() =>
              navigate('/reset-password', {
                state: { email: sentToEmail },
              })
            }
          >
            Enter reset code
          </Button>

          <Button
            variant="ghost"
            className="mt-2 w-full"
            onClick={() => setSentToEmail(null)}
          >
            Send to a different email
          </Button>
        </div>
      </AuthLayout>
    );
  }

  // ── Form screen ──
  return (
    <AuthLayout>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Forgot password?</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Enter the email associated with your account and we'll send you a
          reset code.
        </p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
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
                    autoFocus
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
            {submitting ? 'Sending code…' : 'Send reset code'}
          </Button>
        </form>
      </Form>

      <p className="mt-8 text-center text-sm text-muted-foreground">
        Remembered your password?{' '}
        <Link to="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}