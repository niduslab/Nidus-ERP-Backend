// frontend/src/pages/auth/verify-email-page.tsx
//
// The OTP verification page after registration.
//
// ENTRY:
//   Reached via navigate('/verify-email', { state: { email } }) from
//   the register page. We READ the email out of router state. If the
//   user lands here directly (no state), we redirect to /register.
//
// FLOW:
//   1. Show 6-box OTP input
//   2. User types or pastes 6 digits → auto-submits
//   3. On success: log the user in (the backend returns tokens directly
//      on verify-email — we get logged-in state for free) → /dashboard
//   4. On failure: red borders + error toast
//   5. Resend button with 60s countdown — calls /api/auth/resend-otp/

import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate, Navigate } from 'react-router-dom';
import { Loader2, Mail } from 'lucide-react';
import { toast } from 'sonner';

import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/auth-store';
import { getApiErrorMessage } from '@/lib/api-error';
import { AuthLayout } from '@/pages/auth/auth-layout';
import { OtpInput } from '@/components/auth/otp-input';
import { Button } from '@/components/ui/button';

const RESEND_COOLDOWN_SECONDS = 60;


export function VerifyEmailPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);

  // Read email from router state (set by /register on success).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const email = (location.state as any)?.email as string | undefined;

  const [submitting, setSubmitting] = useState(false);
  const [hasError, setHasError] = useState(false);

  // ── Resend cooldown timer ──
  // secondsLeft counts down from RESEND_COOLDOWN_SECONDS to 0. Each
  // tick is driven by setInterval inside useEffect.
  const [secondsLeft, setSecondsLeft] = useState(RESEND_COOLDOWN_SECONDS);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const id = setInterval(() => {
      setSecondsLeft((s) => Math.max(0, s - 1));
    }, 1000);
    // Cleanup function: clear the interval when the component unmounts
    // or before re-running this effect. Without this, the interval
    // would leak forever.
    return () => clearInterval(id);
  }, [secondsLeft]);

  // Guard: if email is missing (user navigated here directly),
  // bounce back to /register.
  if (!email) {
    return <Navigate to="/register" replace />;
  }

  // ── Handlers ──

  async function handleVerify(otpCode: string) {
    setSubmitting(true);
    setHasError(false);

    try {
      const response = await authApi.verifyEmail({ email: email!, otp_code: otpCode });

      // The backend's verify-email endpoint logs the user in: response
      // includes user + tokens. So we set auth state directly and skip
      // the login page entirely — much smoother UX.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data = (response as any).data;
      if (data?.user && data?.tokens) {
        setAuth({
          user: data.user,
          accessToken: data.tokens.access,
          refreshToken: data.tokens.refresh,
        });
        toast.success(`Welcome to Nidus ERP, ${data.user.full_name.split(' ')[0]}!`);
        navigate('/dashboard', { replace: true });
      } else {
        // Backend doesn't return tokens on verify? Send them to login.
        toast.success('Email verified! Please sign in.');
        navigate('/login', { replace: true });
      }
    } catch (err) {
      setHasError(true);
      toast.error(getApiErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResend() {
    if (secondsLeft > 0) return;
    try {
      await authApi.resendOtp({ email: email! });
      toast.success('A new verification code is on its way.');
      setSecondsLeft(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  }

  return (
    <AuthLayout>
      {/* ── Header with mail icon ── */}
      <div className="mb-8 text-center">
        <div className="mx-auto h-12 w-12 rounded-full bg-accent flex items-center justify-center">
          <Mail className="h-6 w-6 text-accent-foreground" />
        </div>
        <h1 className="mt-4 text-3xl font-bold tracking-tight">
          Verify your email
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          We've sent a 6-digit code to{' '}
          <span className="font-medium text-foreground">{email}</span>
        </p>
      </div>

      {/* ── OTP boxes ── */}
      <div className="space-y-6">
        <OtpInput
          length={6}
          onComplete={handleVerify}
          disabled={submitting}
          hasError={hasError}
        />

        {/* Spinner appears below the boxes during submit */}
        {submitting && (
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Verifying…
          </div>
        )}

        {/* ── Resend block ── */}
        <div className="text-center text-sm text-muted-foreground">
          {secondsLeft > 0 ? (
            <span>
              Didn't get the code? You can request another in{' '}
              <span className="font-mono font-medium text-foreground">
                {secondsLeft}s
              </span>
            </span>
          ) : (
            <Button
              type="button"
              variant="link"
              onClick={handleResend}
              className="h-auto p-0 text-sm"
            >
              Resend verification code
            </Button>
          )}
        </div>
      </div>

      {/* ── Footer link back to register ── */}
      <p className="mt-8 text-center text-sm text-muted-foreground">
        Wrong email?{' '}
        <Link to="/register" className="font-medium text-primary hover:underline">
          Start over
        </Link>
      </p>
    </AuthLayout>
  );
}
