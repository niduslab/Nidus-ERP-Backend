// frontend/src/pages/auth/register-page.tsx
//
// The registration page. Reuses AuthLayout for the split-screen branding.
//
// FORM FIELDS:
//   - email          (required, valid email format)
//   - full_name      (required, 2..120 chars)
//   - phone          (optional, BD format if present)
//   - password       (required, min 8 chars, with strength meter)
//   - password_confirm (required, must match password)
//
// AFTER SUCCESS:
//   The backend has sent an OTP to the user's email. We redirect to
//   /verify-email with the email pre-filled in router state.

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { AxiosError } from 'axios';

import { authApi } from '@/api/auth';
import { getApiErrorMessage, getFieldErrors } from '@/lib/api-error';
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
  FormDescription,
} from '@/components/ui/form';

// ─────────────────────────────────────────────────────
// Zod schema — matches backend RegisterSerializer
// ─────────────────────────────────────────────────────
//
// Validation rules deliberately mirror your Django RegisterSerializer.
// Keeping client + server validation in sync is the senior-engineer
// move — users get instant feedback, server still has the final say.
const registerSchema = z
  .object({
    email: z
      .string()
      .min(1, 'Email is required')
      .email('Please enter a valid email address'),

    full_name: z
      .string()
      .min(2, 'Name must be at least 2 characters')
      .max(120, 'Name is too long'),

    // Bangladesh phone format: optional. If provided, must look like a phone.
    // Accept: +8801XXXXXXXXX, 8801XXXXXXXXX, 01XXXXXXXXX
    // We're lenient here — backend can do stricter validation.
    phone: z
      .string()
      .optional()
      .refine(
        (v) => !v || /^(\+?880|0)?1[3-9]\d{8}$/.test(v.replace(/\s+/g, '')),
        'Please enter a valid Bangladesh phone number',
      ),

    password: z
      .string()
      .min(8, 'Password must be at least 8 characters'),

    password_confirm: z.string().min(1, 'Please confirm your password'),
  })
  // Cross-field validation: passwords must match.
  // .refine runs AFTER each individual field's validation passes.
  // The path: ['password_confirm'] tells Zod where to attach the error.
  .refine((data) => data.password === data.password_confirm, {
    message: 'Passwords do not match',
    path: ['password_confirm'],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;


export function RegisterPage() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: '',
      full_name: '',
      phone: '',
      password: '',
      password_confirm: '',
    },
    mode: 'onBlur',
  });

  // form.watch('password') gives us live updates as the user types.
  // We pass this to the strength meter so it updates in real time.
  // form.watch('email') and 'full_name' feed user-context info to zxcvbn
  // so it can flag passwords that resemble the user's name or email.
  const password = form.watch('password');
  const email = form.watch('email');
  const fullName = form.watch('full_name');

  async function onSubmit(values: RegisterFormValues) {
    setSubmitting(true);

    try {
      await authApi.register(values);

      toast.success('Account created! Check your email for a verification code.');

      // Redirect to OTP verify page, pre-filling the email in router state.
      // The OTP page reads location.state.email to display + use it.
      navigate('/verify-email', {
        replace: true,
        state: { email: values.email },
      });
    } catch (err) {
      // ── Field-level errors (from a 400) ──
      // If the backend sends { errors: { email: ['Already registered'] } }
      // we surface those on the corresponding form fields.
      if (err instanceof AxiosError && err.response?.status === 400) {
        const fieldErrors = getFieldErrors(err);
        let attached = false;
        for (const [field, message] of Object.entries(fieldErrors)) {
          // Only attach if it's a known field on our form.
          if (field in values) {
            form.setError(field as keyof RegisterFormValues, { message });
            attached = true;
          }
        }
        // If we attached at least one field error, no need for a toast.
        if (attached) {
          setSubmitting(false);
          return;
        }
      }

      // Non-field errors → toast.
      toast.error(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <div className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight">Create your account</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Get started with Nidus ERP. We'll send you a code to verify your email.
        </p>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">

          {/* Full name */}
          <FormField
            control={form.control}
            name="full_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Full name</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Rahim Ahmed"
                    autoComplete="name"
                    autoFocus
                    disabled={submitting}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Email */}
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
                    disabled={submitting}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Phone (optional) */}
          <FormField
            control={form.control}
            name="phone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  Phone <span className="text-muted-foreground font-normal">(optional)</span>
                </FormLabel>
                <FormControl>
                  <Input
                    type="tel"
                    placeholder="+8801XXXXXXXXX"
                    autoComplete="tel"
                    disabled={submitting}
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  Bangladesh format. Used for invoice contact info, not required.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Password + strength meter */}
          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Password</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    autoComplete="new-password"
                    disabled={submitting}
                    {...field}
                  />
                </FormControl>
                {/* Live strength meter — uses password + email + name as context */}
                <PasswordStrengthMeter
                  password={password}
                  userInputs={[email, fullName].filter(Boolean)}
                />
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Confirm password */}
          <FormField
            control={form.control}
            name="password_confirm"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Confirm password</FormLabel>
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
            {submitting ? 'Creating account…' : 'Create account'}
          </Button>
        </form>
      </Form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}