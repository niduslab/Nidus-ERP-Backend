# backend/authentication/views.py

import secrets                                   # Cryptographically secure OTP (replaces random.randint)
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import (
    RegisterSerializer,
    VerifyEmailSerializer,
    ResendOTPSerializer,
    LoginSerializer,
    UserProfileSerializer,
    # Phase 2 additions:
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)


User = get_user_model()


def generate_otp():
    return str(secrets.randbelow(900000) + 100000)


class RegisterView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Registration failed. Please check your input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()

        otp_code = generate_otp()
        user.email_verification_code = otp_code
        user.email_verification_code_expires = (
            timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        )
        user.save(update_fields=[
            'email_verification_code',
            'email_verification_code_expires',
        ])

        # CHANGE: Uses centralized email service instead of raw send_mail
        from nidus_erp.email_service import send_verification_email
        send_verification_email(user=user, otp_code=otp_code)

        return Response(
            {
                'success': True,
                'message': f'Registration successful! A verification code has been sent to {user.email}.',
                'data': {
                    'user_id': str(user.id),
                    'email': user.email,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower().strip()
        otp_code = serializer.validated_data['otp_code']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'No account found with this email address.',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_email_verified:
            return Response(
                {
                    'success': False,
                    'message': 'This email is already verified. You can log in.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.email_verification_code != otp_code:
            return Response(
                {
                    'success': False,
                    'message': 'Invalid verification code. Please try again.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timezone.now() > user.email_verification_code_expires:
            return Response(
                {
                    'success': False,
                    'message': 'Verification code has expired. Please request a new one.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_email_verified = True
        user.email_verification_code = None
        user.email_verification_code_expires = None
        user.save(update_fields=[
            'is_email_verified',
            'email_verification_code',
            'email_verification_code_expires',
        ])

        # CHANGE: Lazy import instead of top-level import
        from companies.models import PendingInvitation, CompanyUser

        pending_invitations = PendingInvitation.objects.filter(
            email=email,
            is_accepted=False,
        ).select_related('company')

        companies_joined = []
        for invitation in pending_invitations:
            CompanyUser.objects.create(
                user=user,
                company=invitation.company,
                role=invitation.role,
                invited_by=invitation.invited_by,
            )
            invitation.is_accepted = True
            invitation.save(update_fields=['is_accepted'])
            companies_joined.append(invitation.company.name)

        # CHANGE: Send welcome email with companies list
        from nidus_erp.email_service import send_welcome_email
        send_welcome_email(user=user, companies_joined=companies_joined)

        joined_msg = ''
        if companies_joined:
            joined_msg = f' You have been added to: {", ".join(companies_joined)}.'

        from rest_framework_simplejwt.tokens import RefreshToken
        from authentication.serializers import UserProfileSerializer

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'success': True,
                'message': f'Email verified successfully!{joined_msg}',
                'data': {
                    'user': UserProfileSerializer(user).data,
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh),
                    },
                },
            },
            status=status.HTTP_200_OK,
        )


class ResendOTPView(APIView):

    permission_classes = [AllowAny]

    # ── Rate limiting ──
    # 5 requests per hour per IP. This endpoint sends an email on each
    # successful hit, so the limit is tighter than login to prevent:
    #   (1) Harassing a known user with a flood of OTP emails
    #   (2) SMTP cost abuse
    from rest_framework.throttling import ScopedRateThrottle
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'anon_resend_otp'

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower().strip()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {
                    'success': True,
                    'message': 'If an account with this email exists, a new code has been sent.',
                },
                status=status.HTTP_200_OK,
            )

        if user.is_email_verified:
            return Response(
                {
                    'success': False,
                    'message': 'This email is already verified.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_code = generate_otp()
        user.email_verification_code = otp_code
        user.email_verification_code_expires = (
            timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        )
        user.save(update_fields=[
            'email_verification_code',
            'email_verification_code_expires',
        ])

        # CHANGE: Uses centralized email service
        from nidus_erp.email_service import send_verification_email
        send_verification_email(user=user, otp_code=otp_code)

        return Response(
            {
                'success': True,
                'message': 'If an account with this email exists, a new code has been sent.',
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):

    permission_classes = [AllowAny]

    # ── Rate limiting ──
    # ScopedRateThrottle looks up the `throttle_scope` name in
    # settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']. Anonymous requests
    # are keyed by IP, so each IP gets at most 10 login attempts per minute.
    # Applies to BOTH valid and invalid credentials — an attacker guessing
    # passwords can't avoid the counter by failing fast.
    from rest_framework.throttling import ScopedRateThrottle
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'anon_login'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower().strip()
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Invalid email or password.',
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.check_password(password):
            return Response(
                {
                    'success': False,
                    'message': 'Invalid email or password.',
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {
                    'success': False,
                    'message': 'This account has been deactivated. Please contact support.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not user.is_email_verified:
            # ── Auto-recovery: re-send a fresh OTP so the user can complete
            #    verification, even if they abandoned registration earlier.
            # This closes the "stuck email" loop where a user couldn't
            # register, log in, OR re-trigger verification with that email.
            #
            # Rate-limiting is already enforced on the login endpoint
            # (10/min per IP via ScopedRateThrottle), so this can't be abused
            # to mass-generate OTP emails.
            from nidus_erp.email_service import send_verification_email

            otp_code = generate_otp()
            user.email_verification_code = otp_code
            user.email_verification_code_expires = (
                timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
            )
            user.save(update_fields=[
                'email_verification_code',
                'email_verification_code_expires',
            ])
            send_verification_email(user=user, otp_code=otp_code)

            return Response(
                {
                    'success': False,
                    'message': 'Your email is not verified. We just sent a new verification code.',
                    'requires_verification': True,
                    'email': user.email,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        return Response(
            {
                'success': True,
                'message': 'Login successful!',
                'data': {
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh),
                    },
                    'user': UserProfileSerializer(user).data,
                },
            },
            status=status.HTTP_200_OK,
        )


class ProfileView(APIView):

    def get(self, request):
        serializer = UserProfileSerializer(request.user)

        return Response(
            {
                'success': True,
                'data': serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):

    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {
                    'success': False,
                    'message': 'Refresh token is required.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {
                    'success': True,
                    'message': 'Logged out successfully.',
                },
                status=status.HTTP_200_OK,
            )

        except TokenError:
            return Response(
                {
                    'success': False,
                    'message': 'Token is invalid or already expired.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
# ══════════════════════════════════════════════════
# PASSWORD RESET FLOW (Phase 2)
# ══════════════════════════════════════════════════
#
# Two-step, OTP-based, consistent with the existing email-verification UX.
#
#   Step 1 — POST /api/auth/forgot-password/   {email}
#            → Sends a 6-digit OTP to the email if the account exists.
#            → Always returns HTTP 200 with a generic message, regardless
#              of whether the email exists. This prevents account enumeration.
#
#   Step 2 — POST /api/auth/reset-password/    {email, otp_code, new_password, new_password_confirm}
#            → Validates OTP (exists + matches + not expired).
#            → Updates the password.
#            → BLACKLISTS every outstanding refresh token for this user so
#              all active sessions on all devices are terminated. If the
#              account was compromised, the attacker is forcibly logged out.

class ForgotPasswordView(APIView):
    """
    Step 1 of password reset. Accepts an email, generates a 6-digit OTP,
    stores it on the User with an expiry, and emails the OTP via the
    centralized email service.

    RESPONSE BEHAVIOUR — INTENTIONALLY OPAQUE:
        We always return HTTP 200 with the same message whether the email
        belongs to a real user or not. Returning a distinguishable error
        would let attackers enumerate valid emails with a wordlist. Also
        matches the existing ResendOTPView pattern.
    """

    permission_classes = [AllowAny]

    # ── Rate limiting ──
    # 5 requests per hour per IP — prevents email flooding of a target address
    # and constrains SMTP cost abuse.
    from rest_framework.throttling import ScopedRateThrottle
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'anon_forgot_password'

    # Generic response repeated on every exit path so behaviour is identical
    # whether the email exists, is unverified, or is totally bogus.
    GENERIC_RESPONSE = {
        'success': True,
        'message': 'If an account with this email exists, a password reset code has been sent.',
    }

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            # Bad input (e.g., not an email) — we can safely surface validation
            # errors because they're about the input shape, not account existence.
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower().strip()

        # ── Look up the user silently ──
        # DoesNotExist falls through to the generic success response below.
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(self.GENERIC_RESPONSE, status=status.HTTP_200_OK)

        # ── Refuse to send reset codes to unverified or inactive accounts ──
        # Still using the generic response — no information leakage. An
        # unverified user should complete email verification first; an
        # inactive user has been deactivated and needs admin intervention.
        if not user.is_email_verified or not user.is_active:
            return Response(self.GENERIC_RESPONSE, status=status.HTTP_200_OK)

        # ── Generate OTP and persist ──
        otp_code = generate_otp()   # Uses secrets.randbelow — cryptographically secure
        user.password_reset_code = otp_code
        user.password_reset_code_expires = (
            timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        )
        user.save(update_fields=[
            'password_reset_code',
            'password_reset_code_expires',
        ])

        # ── Send the email ──
        # Lazy import matches the existing pattern in RegisterView/VerifyEmailView.
        from nidus_erp.email_service import send_password_reset_email
        send_password_reset_email(user=user, otp_code=otp_code)

        return Response(self.GENERIC_RESPONSE, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """
    Step 2 of password reset. Validates the OTP and, on success, updates
    the password and terminates every existing session for the user.

    FORCED LOGOUT ON SUCCESS:
        Every refresh token belonging to the user is blacklisted. This is
        critical: if the reset was triggered because the account was
        compromised, we must eject the attacker even if they currently hold
        a valid access token. Note that access tokens live up to
        ACCESS_TOKEN_LIFETIME (24h in this project); the attacker could
        still use an existing access token until it expires, but they
        cannot refresh it, so the window is bounded.
    """

    permission_classes = [AllowAny]

    # ── Rate limiting ──
    # 10 requests per hour per IP. This protects against OTP brute-forcing
    # of the 6-digit code. With 10^6 combinations and 10/hour, a
    # brute-force attack would need ~100k hours to exhaust the space —
    # well beyond the OTP's 10-minute expiry window.
    from rest_framework.throttling import ScopedRateThrottle
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'anon_reset_password'

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'message': 'Invalid input.',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data['email'].lower().strip()
        otp_code = serializer.validated_data['otp_code']
        new_password = serializer.validated_data['new_password']

        # ── Locate the user ──
        # For the reset step we DO return a 400 when the account is missing/
        # invalid, because by this point the attacker already has to know a
        # valid OTP — an 8-digit OTP attack is the real threat, not
        # enumeration. A clear error here is better UX.
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'success': False, 'message': 'Invalid reset code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Validate the stored OTP ──
        if not user.password_reset_code or user.password_reset_code != otp_code:
            return Response(
                {'success': False, 'message': 'Invalid reset code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.password_reset_code_expires or timezone.now() > user.password_reset_code_expires:
            return Response(
                {
                    'success': False,
                    'message': 'Reset code has expired. Please request a new one.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Commit the password change ──
        # set_password() hashes via PBKDF2/Argon2 per Django's PASSWORD_HASHERS.
        user.set_password(new_password)

        # Clear the OTP so it can't be reused.
        user.password_reset_code = None
        user.password_reset_code_expires = None
        user.save(update_fields=[
            'password',
            'password_reset_code',
            'password_reset_code_expires',
        ])

        # ── Terminate all existing sessions (security best practice) ──
        # Blacklist every outstanding refresh token for this user. Uses
        # SimpleJWT's blacklist app which we already have installed.
        _blacklist_all_refresh_tokens(user)

        return Response(
            {
                'success': True,
                'message': (
                    'Password has been reset successfully. '
                    'All active sessions have been terminated — please log in again.'
                ),
            },
            status=status.HTTP_200_OK,
        )


# ──────────────────────────────────────────────
# PASSWORD RESET HELPERS
# ──────────────────────────────────────────────

def _blacklist_all_refresh_tokens(user):
    """
    Blacklist every outstanding refresh token for the given user.

    Called after a successful password reset to force all sessions on all
    devices to re-authenticate. Safe to call even if the user has never
    logged in (the queryset is simply empty).

    IMPLEMENTATION NOTES:
        - Uses SimpleJWT's token_blacklist app — already in INSTALLED_APPS.
        - OutstandingToken is the registry of every refresh token ever issued.
        - BlacklistedToken marks a token as revoked. Once blacklisted, any
          future refresh attempt with that token raises TokenError.
        - We use get_or_create to avoid IntegrityError if a token is already
          blacklisted (e.g., the user previously logged out).
        - Does NOT invalidate access tokens — SimpleJWT has no access-token
          blacklist by default. The attacker could still use an existing
          access token until it expires (ACCESS_TOKEN_LIFETIME). Given this
          project chose 24h access tokens, that is the trade-off.
    """
    from rest_framework_simplejwt.token_blacklist.models import (
        OutstandingToken,
        BlacklistedToken,
    )

    outstanding = OutstandingToken.objects.filter(user=user)
    for token in outstanding:
        BlacklistedToken.objects.get_or_create(token=token)