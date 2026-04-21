# backend/authentication/tests/test_profile_and_logout.py
#
# Tests for the small but important protected endpoints:
#   GET  /api/auth/profile/         — current user details
#   POST /api/auth/logout/          — blacklists the caller's refresh token
#   POST /api/auth/token/refresh/   — rotates access+refresh tokens

import pytest
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken


PROFILE_URL = reverse('authentication:profile')
LOGOUT_URL = reverse('authentication:logout')
TOKEN_REFRESH_URL = reverse('authentication:token-refresh')


@pytest.mark.django_db
class TestProfile:

    def test_returns_current_user(self, authed_client, verified_user):
        """GET /profile/ returns the logged-in user's data, no password hash."""
        response = authed_client.get(PROFILE_URL)
        assert response.status_code == 200
        data = response.data['data']
        assert data['email'] == verified_user.email
        # Password should never appear in API responses.
        assert 'password' not in data

    def test_rejects_anonymous(self, api_client):
        """No token → 401."""
        response = api_client.get(PROFILE_URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestLogout:

    def test_blacklists_refresh_token(self, authed_client, verified_user):
        """
        Happy path — POST /logout/ with a refresh token blacklists it,
        so a subsequent token/refresh/ call using the same token fails.
        """
        refresh = RefreshToken.for_user(verified_user)
        refresh_str = str(refresh)

        response = authed_client.post(
            LOGOUT_URL, {'refresh': refresh_str}, format='json',
        )
        assert response.status_code == 200

        # Verify: the refresh token is now blacklisted.
        verify_resp = authed_client.post(
            TOKEN_REFRESH_URL, {'refresh': refresh_str}, format='json',
        )
        assert verify_resp.status_code == 401

    def test_logout_requires_refresh_token(self, authed_client):
        """Missing 'refresh' in body → 400."""
        response = authed_client.post(LOGOUT_URL, {}, format='json')
        assert response.status_code == 400