# backend/authentication/tests/test_login.py
#
# Tests for POST /api/auth/login/ — the JWT issue endpoint.
# Also covers the built-in rate-limit (10/min per IP) added in Phase 2.

import pytest
from django.urls import reverse


LOGIN_URL = reverse('authentication:login')


@pytest.mark.django_db
class TestLogin:

    def test_logs_in_verified_user(self, api_client, verified_user):
        """Happy path — correct credentials return access + refresh tokens."""
        response = api_client.post(LOGIN_URL, {
            'email': verified_user.email,
            'password': 'TestPassword123!',   # Factory default
        }, format='json')

        assert response.status_code == 200
        tokens = response.data['data']['tokens']
        assert 'access' in tokens
        assert 'refresh' in tokens
        # Tokens are non-empty JWTs (3 base64 segments separated by dots).
        assert tokens['access'].count('.') == 2
        assert tokens['refresh'].count('.') == 2

    def test_rejects_wrong_password(self, api_client, verified_user):
        """Wrong password → 401 with a GENERIC message (no "user not found" leak)."""
        response = api_client.post(LOGIN_URL, {
            'email': verified_user.email,
            'password': 'WrongPassword!',
        }, format='json')

        assert response.status_code == 401

    def test_rejects_nonexistent_email(self, api_client):
        """Unknown email → same 401 as wrong password (anti-enumeration)."""
        response = api_client.post(LOGIN_URL, {
            'email': 'nobody@example.com',
            'password': 'Anything123!',
        }, format='json')

        assert response.status_code == 401
        # The message MUST match what a wrong-password response returns,
        # otherwise attackers can enumerate valid emails.
        assert 'invalid email or password' in response.data['message'].lower()

    def test_rejects_unverified_user(self, api_client, unverified_user):
        """Unverified accounts cannot log in — they must complete OTP flow first."""
        # unverified_user comes from the factory with a known password.
        unverified_user.set_password('TestPassword123!')
        unverified_user.save()

        response = api_client.post(LOGIN_URL, {
            'email': unverified_user.email,
            'password': 'TestPassword123!',
        }, format='json')

        assert response.status_code == 403
        # The view returns `requires_verification: True` so the frontend can
        # route the user to the OTP screen. Assert on that signal.
        assert response.data.get('requires_verification') is True

    def test_rejects_deactivated_user(self, api_client, verified_user):
        """An admin-disabled account cannot log in."""
        verified_user.is_active = False
        verified_user.save()

        response = api_client.post(LOGIN_URL, {
            'email': verified_user.email,
            'password': 'TestPassword123!',
        }, format='json')

        assert response.status_code == 403

    @pytest.mark.slow
    def test_enforces_rate_limit(self, api_client):
        """
        Rate limit: 10 attempts/min per IP (see settings.REST_FRAMEWORK
        DEFAULT_THROTTLE_RATES['anon_login']).

        We fire 11 login attempts — attempts 1-10 get 401 (bad credentials),
        attempt 11 gets 429 (rate limited).
        """
        payload = {'email': 'noone@example.com', 'password': 'wrong'}

        for i in range(10):
            response = api_client.post(LOGIN_URL, payload, format='json')
            assert response.status_code == 401, f'Attempt {i+1}: expected 401, got {response.status_code}'

        response = api_client.post(LOGIN_URL, payload, format='json')
        assert response.status_code == 429