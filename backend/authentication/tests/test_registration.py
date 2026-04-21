# backend/authentication/tests/test_registration.py
#
# Tests for the registration endpoint: POST /api/auth/register/
#
# Covers the happy path, validation failures, and the email-uniqueness
# constraint. Does NOT test verification / login — those have their own files.

import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

from authentication.factories import UserFactory


User = get_user_model()
REGISTER_URL = reverse('authentication:register')


@pytest.mark.django_db
class TestRegistration:
    """
    Registration endpoint tests.

    Using a class to group related tests gives nicer pytest output:
        test_registration.py::TestRegistration::test_registers_valid_user
    And allows class-level markers (e.g., @pytest.mark.slow) if we need them.
    """

    def test_registers_valid_user(self, api_client):
        """Happy path — valid input creates a User in the DB with is_email_verified=False."""
        response = api_client.post(REGISTER_URL, {
            'email': 'newuser@example.com',
            'full_name': 'New User',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
        }, format='json')

        assert response.status_code == 201, response.data
        assert response.data['success'] is True
        assert response.data['data']['email'] == 'newuser@example.com'

        # Verify the user was actually persisted.
        user = User.objects.get(email='newuser@example.com')
        assert user.is_email_verified is False          # Must verify before login
        assert user.check_password('StrongPass123!')    # Password hashed, not plain

    def test_registration_normalises_email_case(self, api_client):
        """Emails should be lower-cased on save — the unique constraint is case-insensitive in intent."""
        response = api_client.post(REGISTER_URL, {
            'email': 'Mixed.Case@Example.COM',
            'full_name': 'Test User',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
        }, format='json')

        assert response.status_code == 201
        assert User.objects.filter(email='mixed.case@example.com').exists()

    def test_rejects_mismatched_passwords(self, api_client):
        """password_confirm must match password — a common user error worth validating."""
        response = api_client.post(REGISTER_URL, {
            'email': 'user@example.com',
            'full_name': 'User',
            'password': 'StrongPass123!',
            'password_confirm': 'DifferentPass!',
        }, format='json')

        assert response.status_code == 400
        # DRF serializer errors land under response.data['errors'] in this project.
        assert 'password_confirm' in response.data['errors']

    def test_rejects_weak_password(self, api_client):
        """Django's AUTH_PASSWORD_VALIDATORS must reject trivial passwords."""
        response = api_client.post(REGISTER_URL, {
            'email': 'user@example.com',
            'full_name': 'User',
            # 'password' is in the top-10 most common passwords — CommonPasswordValidator rejects it.
            'password': 'password',
            'password_confirm': 'password',
        }, format='json')

        assert response.status_code == 400

    def test_rejects_duplicate_email(self, api_client, verified_user):
        """Attempting to register an email that already exists must fail cleanly."""
        response = api_client.post(REGISTER_URL, {
            'email': verified_user.email,
            'full_name': 'Different User',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
        }, format='json')

        assert response.status_code == 400
        # The email validator in RegisterSerializer raises; errors nested under 'email'.
        assert 'email' in response.data['errors']

    def test_rejects_invalid_email_format(self, api_client):
        """Malformed emails must be rejected by the EmailField validator."""
        response = api_client.post(REGISTER_URL, {
            'email': 'not-an-email',
            'full_name': 'User',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
        }, format='json')

        assert response.status_code == 400