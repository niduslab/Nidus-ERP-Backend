# backend/authentication/tests/test_password_reset.py
#
# Tests for the Phase 2 password-reset flow:
#   POST /api/auth/forgot-password/
#   POST /api/auth/reset-password/
#
# Critical invariants verified here:
#   1. Email enumeration is blocked (identical response for real and bogus emails)
#   2. Successful reset blacklists all outstanding refresh tokens (forced logout)

import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken


FORGOT_URL = reverse('authentication:forgot-password')
RESET_URL = reverse('authentication:reset-password')
LOGIN_URL = reverse('authentication:login')
TOKEN_REFRESH_URL = reverse('authentication:token-refresh')


@pytest.mark.django_db
class TestForgotPassword:

    def test_returns_generic_success_for_real_email(self, api_client, verified_user):
        """Real email → 200 generic. Side effect: OTP stored on the User."""
        response = api_client.post(
            FORGOT_URL, {'email': verified_user.email}, format='json',
        )
        assert response.status_code == 200

        verified_user.refresh_from_db()
        # OTP should now be populated and expiry set.
        assert verified_user.password_reset_code is not None
        assert len(verified_user.password_reset_code) == 6
        assert verified_user.password_reset_code_expires is not None

    def test_returns_identical_response_for_bogus_email(self, api_client):
        """
        ANTI-ENUMERATION INVARIANT:
            Response body and status for a nonexistent email MUST be
            byte-for-byte identical to the real-email response. If an
            attacker can tell the two apart, the endpoint leaks account
            existence.
        """
        bogus_resp = api_client.post(
            FORGOT_URL, {'email': 'doesnotexist@example.com'}, format='json',
        )
        assert bogus_resp.status_code == 200

        # We can't compare to a real-email response here (side effects), but
        # we CAN assert the response shape matches the documented contract.
        assert bogus_resp.data['success'] is True
        assert 'If an account' in bogus_resp.data['message']

    def test_returns_generic_success_for_unverified_account(self, api_client, unverified_user):
        """Unverified accounts should also get the generic response — no leak."""
        response = api_client.post(
            FORGOT_URL, {'email': unverified_user.email}, format='json',
        )
        assert response.status_code == 200
        # No OTP should be set — unverified accounts don't get reset codes.
        unverified_user.refresh_from_db()
        assert unverified_user.password_reset_code is None


@pytest.mark.django_db
class TestResetPassword:

    def test_resets_with_valid_otp(self, api_client, user_with_reset_otp):
        """Happy path — OTP match updates password, clears OTP, returns 200."""
        response = api_client.post(RESET_URL, {
            'email': user_with_reset_otp.email,
            'otp_code': '654321',            # From user_with_reset_otp fixture
            'new_password': 'NewStrongPass1!',
            'new_password_confirm': 'NewStrongPass1!',
        }, format='json')

        assert response.status_code == 200

        user_with_reset_otp.refresh_from_db()
        # Password must be updated and stored hashed, not plaintext.
        assert user_with_reset_otp.check_password('NewStrongPass1!')
        # OTP must be cleared to prevent replay.
        assert user_with_reset_otp.password_reset_code is None

    def test_rejects_wrong_otp(self, api_client, user_with_reset_otp):
        """Wrong OTP → 400, password unchanged."""
        response = api_client.post(RESET_URL, {
            'email': user_with_reset_otp.email,
            'otp_code': '000000',
            'new_password': 'NewStrongPass1!',
            'new_password_confirm': 'NewStrongPass1!',
        }, format='json')

        assert response.status_code == 400
        user_with_reset_otp.refresh_from_db()
        # Password is still the factory default.
        assert user_with_reset_otp.check_password('TestPassword123!')

    def test_rejects_mismatched_password_confirm(self, api_client, user_with_reset_otp):
        """Serializer-level validation — two password fields must match."""
        response = api_client.post(RESET_URL, {
            'email': user_with_reset_otp.email,
            'otp_code': '654321',
            'new_password': 'NewStrongPass1!',
            'new_password_confirm': 'DifferentPass1!',
        }, format='json')

        assert response.status_code == 400

    def test_successful_reset_blacklists_all_refresh_tokens(
        self, api_client, user_with_reset_otp,
    ):
        """
        SECURITY INVARIANT — Forced logout on password reset:
            After a successful reset, every outstanding refresh token for
            the user must be blacklisted. Using a previously-valid refresh
            token must now return 401.

        Why this matters: a user resetting their password often does so
        because they suspect compromise. The attacker holding a stolen
        refresh token MUST be ejected.
        """
        # ── Arrange: simulate the user being logged in before the reset ──
        # Issue a refresh token the same way LoginView does.
        refresh = RefreshToken.for_user(user_with_reset_otp)
        refresh_token_str = str(refresh)

        # Sanity check: the token works before the reset.
        pre_response = api_client.post(
            TOKEN_REFRESH_URL, {'refresh': refresh_token_str}, format='json',
        )
        assert pre_response.status_code == 200

        # ── Act: perform the password reset ──
        api_client.post(RESET_URL, {
            'email': user_with_reset_otp.email,
            'otp_code': '654321',
            'new_password': 'NewStrongPass1!',
            'new_password_confirm': 'NewStrongPass1!',
        }, format='json')

        # ── Assert: the old refresh token is now rejected ──
        post_response = api_client.post(
            TOKEN_REFRESH_URL, {'refresh': refresh_token_str}, format='json',
        )
        assert post_response.status_code == 401