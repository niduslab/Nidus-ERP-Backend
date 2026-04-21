# backend/authentication/tests/test_verify_email.py
#
# Tests for POST /api/auth/verify-email/ — the OTP verification flow that
# activates a freshly registered account.

import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from freezegun import freeze_time


VERIFY_URL = reverse('authentication:verify-email')


@pytest.mark.django_db
class TestVerifyEmail:

    def test_verifies_with_correct_otp(self, api_client, user_with_otp):
        """Happy path — correct OTP flips is_email_verified and clears the code."""
        response = api_client.post(VERIFY_URL, {
            'email': user_with_otp.email,
            'otp_code': '123456',   # Matches the fixture-set OTP
        }, format='json')

        assert response.status_code == 200
        user_with_otp.refresh_from_db()
        assert user_with_otp.is_email_verified is True
        # The OTP must be cleared after use so it can't be replayed.
        assert user_with_otp.email_verification_code is None
        assert user_with_otp.email_verification_code_expires is None

    def test_rejects_wrong_otp(self, api_client, user_with_otp):
        """Wrong code → 400 and account stays unverified."""
        response = api_client.post(VERIFY_URL, {
            'email': user_with_otp.email,
            'otp_code': '999999',
        }, format='json')

        assert response.status_code == 400
        user_with_otp.refresh_from_db()
        assert user_with_otp.is_email_verified is False

    def test_rejects_expired_otp(self, api_client, user_with_otp):
        """
        OTP expires OTP_EXPIRY_MINUTES after issue (default 10 min).

        freezegun travels time forward by 11 minutes so the OTP in the
        fixture is now stale, without actually waiting. Faster and
        deterministic compared to setting fixture expiry in the past.
        """
        with freeze_time(timezone.now() + timedelta(minutes=11)):
            response = api_client.post(VERIFY_URL, {
                'email': user_with_otp.email,
                'otp_code': '123456',
            }, format='json')

        assert response.status_code == 400
        assert 'expired' in response.data['message'].lower()

    def test_rejects_unknown_email(self, api_client):
        """Nonexistent email → 404. Unlike forgot-password, verify IS informative
        (the attacker would have needed the OTP anyway, and a clear error helps
        the user understand a typo in the email)."""
        response = api_client.post(VERIFY_URL, {
            'email': 'nobody@example.com',
            'otp_code': '123456',
        }, format='json')

        assert response.status_code == 404

    def test_rejects_already_verified(self, api_client, verified_user):
        """A user who is already verified can't re-verify — their OTP is None anyway."""
        response = api_client.post(VERIFY_URL, {
            'email': verified_user.email,
            'otp_code': '123456',
        }, format='json')

        assert response.status_code == 400
        assert 'already verified' in response.data['message'].lower()