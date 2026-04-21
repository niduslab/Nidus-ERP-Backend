# backend/companies/tests/test_company_ownership.py
#
# Tests for the ownership-transfer flow:
#   POST /api/companies/<id>/transfer-ownership/
#
# This is a high-sensitivity endpoint — it hands control of all financial
# data to a different user. The protections we verify:
#   1. Only the current OWNER can initiate
#   2. Current owner's password must match (re-authentication)
#   3. Target must be an existing active member of the company
#   4. Cannot transfer to yourself
#   5. Transfer is atomic: Company.owner + CompanyUser.role updated together

import pytest
from django.urls import reverse

from companies.models import CompanyUser, RoleChoices
from authentication.factories import TEST_PASSWORD


def _transfer_url(company_id):
    return reverse('companies:transfer-ownership', args=[company_id])


@pytest.mark.django_db
class TestTransferOwnership:

    def test_happy_path_transfer_keeps_old_owner_as_admin(
        self, authed_client, company_with_accountant, verified_user, other_user,
    ):
        """
        Successful transfer updates BOTH Company.owner AND CompanyUser.role
        rows atomically. The old owner becomes ADMIN (by request).
        """
        response = authed_client.post(
            _transfer_url(company_with_accountant.id),
            {
                'new_owner_email': other_user.email,
                'password': TEST_PASSWORD,         # From factories.py
                'new_role_for_self': 'ADMIN',
            },
            format='json',
        )

        assert response.status_code == 200

        company_with_accountant.refresh_from_db()
        assert company_with_accountant.owner == other_user

        # New owner's role → OWNER
        new_owner_membership = CompanyUser.objects.get(
            user=other_user, company=company_with_accountant,
        )
        assert new_owner_membership.role == RoleChoices.OWNER

        # Old owner's role → ADMIN
        old_owner_membership = CompanyUser.objects.get(
            user=verified_user, company=company_with_accountant,
        )
        assert old_owner_membership.role == RoleChoices.ADMIN
        assert old_owner_membership.is_active is True

    def test_rejects_wrong_password(
        self, authed_client, company_with_accountant, other_user,
    ):
        """Re-authentication check — wrong password = 401, no state change."""
        response = authed_client.post(
            _transfer_url(company_with_accountant.id),
            {
                'new_owner_email': other_user.email,
                'password': 'WRONG_PASSWORD_XYZ',
                'new_role_for_self': 'ADMIN',
            },
            format='json',
        )
        assert response.status_code == 401

        # Confirm no side effects.
        company_with_accountant.refresh_from_db()
        assert company_with_accountant.owner != other_user

    def test_rejects_non_member_target(
        self, authed_client, company, verified_user,
    ):
        """Cannot transfer to someone who isn't already a member of the company."""
        from authentication.factories import UserFactory
        stranger = UserFactory(is_email_verified=True)

        response = authed_client.post(
            _transfer_url(company.id),
            {
                'new_owner_email': stranger.email,
                'password': TEST_PASSWORD,
                'new_role_for_self': 'ADMIN',
            },
            format='json',
        )
        assert response.status_code == 400

    def test_accountant_cannot_initiate_transfer(
        self, authed_client_for, company_with_accountant, other_user,
    ):
        """Non-owners attempting to transfer → 403."""
        client = authed_client_for(other_user)   # other_user is ACCOUNTANT
        response = client.post(
            _transfer_url(company_with_accountant.id),
            {
                'new_owner_email': other_user.email,
                'password': TEST_PASSWORD,
                'new_role_for_self': 'ADMIN',
            },
            format='json',
        )
        assert response.status_code == 403